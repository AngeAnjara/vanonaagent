import asyncio
import json
from typing import Any
from xmlrpc import client as xmlrpclib

from python.helpers.tool import Tool, Response
from python.helpers.errors import RepairableException, format_error
from python.helpers.print_style import PrintStyle


_OBSOLETE_FIELD_MAPPING: dict[str, str] = {
    "account.account:user_type_id": "account_type",
    "account.account:type": "account_type",
    "account.account:balance": "current_balance",
    "res.partner:type": "company_type",
}


class OdooCall(Tool):

    _models_cache: dict[str, list[dict[str, Any]]] = {}
    _fields_cache: dict[str, dict[str, Any]] = {}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def execute(self, **kwargs) -> Response:
        # Ensure Odoo integration is enabled in settings
        if not getattr(self.agent.config, "odoo_enabled", False):
            raise RepairableException(
                "Odoo integration is not enabled. Please enable and configure Odoo in Settings > Odoo Integration."
            )

        odoo_url: str = getattr(self.agent.config, "odoo_url", "") or ""
        odoo_db: str = getattr(self.agent.config, "odoo_db", "") or ""
        odoo_user: str = getattr(self.agent.config, "odoo_user", "") or ""
        odoo_password: str = getattr(self.agent.config, "odoo_password", "") or ""

        # Prefer kwargs (if provided) to align with potential external callers, fallback to self.args
        model: str | None = kwargs.get("model", self.args.get("model"))
        method: str | None = kwargs.get("method", self.args.get("method"))
        domain: Any = kwargs.get("domain", self.args.get("domain", []))
        fields: list[str] | None = kwargs.get("fields", self.args.get("fields"))
        options: dict[str, Any] = kwargs.get("options", self.args.get("options", {}))
        ids = kwargs.get("ids", self.args.get("ids"))
        vals = kwargs.get("vals", self.args.get("vals"))
        raw_args = kwargs.get("raw_args", self.args.get("raw_args", []))
        discover_models: bool = kwargs.get("discover_models", self.args.get("discover_models", False))
        discover_fields: str | None = kwargs.get("discover_fields", self.args.get("discover_fields"))

        # Validate configuration
        missing = [
            k
            for k, v in {
                "ODOO_URL": odoo_url,
                "ODOO_DB": odoo_db,
                "ODOO_USER": odoo_user,
                "ODOO_PASSWORD": odoo_password,
            }.items()
            if not v
        ]
        if missing:
            raise RepairableException(
                "Missing Odoo configuration values. Please configure Odoo in Settings > Odoo Integration."
            )
        if not discover_models and not discover_fields and (not model or not method):
            raise RepairableException("'model' and 'method' are required arguments for odoo_call")

        # Build endpoints
        common_url = f"{odoo_url.rstrip('/')}/xmlrpc/2/common"
        object_url = f"{odoo_url.rstrip('/')}/xmlrpc/2/object"

        # Prepare execution in thread to avoid blocking
        def _run() -> Any:
            try:
                common = xmlrpclib.ServerProxy(common_url)
                uid = common.authenticate(odoo_db, odoo_user, odoo_password, {})
                if not uid:
                    raise RepairableException("Authentication to Odoo failed. Check ODOO_USER/ODOO_PASSWORD.")

                models = xmlrpclib.ServerProxy(object_url)

                if discover_models:
                    return self._discover_models(models, odoo_db, uid, odoo_password, odoo_url)

                if discover_fields:
                    return self._discover_fields(models, odoo_db, uid, odoo_password, discover_fields, odoo_url)

                args_list = []
                if method in ("search", "search_read"):
                    args_list = [domain if isinstance(domain, list) else []]
                elif method in ("read", "write", "unlink"):
                    # For read/write/unlink the first positional arg is ids
                    if ids is None:
                        raise RepairableException("'ids' argument is required for method 'read'/'write'/'unlink'")
                    args_list = [ids]
                elif method in ("create",):
                    if vals is None:
                        raise RepairableException("'vals' argument is required for method 'create'")
                    args_list = [vals]
                elif method == "read_group":
                    if "order" in options and "orderby" not in options:
                        options["orderby"] = options.pop("order")
                    groupby = options.get("groupby")
                    if not groupby:
                        raise RepairableException("'groupby' is required in options for read_group")
                    fields_list = fields or options.get("fields", [])
                    if not isinstance(fields_list, list):
                        fields_list = [fields_list]
                    args_list = [domain if isinstance(domain, list) else [], fields_list, groupby]
                    options.pop("fields", None)
                    options.pop("groupby", None)
                else:
                    # generic: allow passing raw 'args' list
                    if not isinstance(raw_args, list):
                        raise RepairableException("'raw_args' must be a list when using generic method")
                    args_list = raw_args

                options_dict: dict[str, Any] = options if isinstance(options, dict) else {}

                kwargs_call: dict[str, Any] = {}
                if fields and method in ("search_read", "read"):
                    kwargs_call["fields"] = fields

                allowed_kwargs_by_method: dict[str, set[str]] = {
                    "search_read": {"fields", "offset", "limit", "order"},
                    "read_group": {"offset", "limit", "orderby", "lazy", "context"},
                    "read": {"fields"},
                    "search": {"offset", "limit", "order"},
                }

                if options_dict:
                    if method in allowed_kwargs_by_method:
                        for key in allowed_kwargs_by_method[method]:
                            if key in options_dict:
                                kwargs_call[key] = options_dict[key]
                    else:
                        kwargs_call.update(options_dict)

                result = models.execute_kw(
                    odoo_db,
                    uid,
                    odoo_password,
                    model,
                    method,
                    args_list,
                    kwargs_call,
                )
                return result
            except RepairableException:
                raise
            except xmlrpclib.Fault as fault:
                message = f"Odoo XML-RPC Fault {fault.faultCode}: {fault.faultString}"
                lower_msg = str(fault.faultString).lower()
                if "unexpected keyword" in lower_msg or "unexpected keyword argument" in lower_msg:
                    message += (
                        " | Hint: Check method-specific parameters. For 'read_group', use 'orderby' instead of 'order' and ensure 'groupby' is provided in options."
                    )
                missing_model_markers = [
                    "does not exist",
                    "n'existe pas",
                    "model not found",
                    "unknown model",
                    "no such model",
                ]
                invalid_field_markers = [
                    "invalid field",
                    "champ invalide",
                    "field not found",
                    "unknown field",
                ]
                structured_message: str | None = None
                suggested_models: list[dict[str, Any]] = []
                invalid_field_payload: dict[str, Any] | None = None
                if any(marker in lower_msg for marker in missing_model_markers):
                    standard_models = [
                        "sale.order",
                        "res.partner",
                        "product.product",
                        "account.move",
                        "stock.picking",
                        "crm.lead",
                        "project.project",
                        "hr.employee",
                        "purchase.order",
                    ]
                    message += (
                        f" | Le modèle '{model}' n'existe pas dans votre instance Odoo ou n'est pas accessible. "
                        "Cela peut signifier que le module correspondant n'est pas installé ou que vous n'avez pas les droits suffisants. "
                        "Modèles standards courants: "
                        + ", ".join(standard_models)
                        + ". Utilisez odoo_call avec model='ir.model' et method='search_read' pour lister les modèles disponibles (voir la documentation de l'outil)."
                    )
                    # Try to discover available business models to provide structured suggestions
                    try:
                        suggested_models = self._discover_models(models, odoo_db, uid, odoo_password, odoo_url)
                    except Exception:
                        suggested_models = []

                    if suggested_models:
                        error_payload = {
                            "error": message,
                            "model": model,
                            "suggested_models": suggested_models,
                        }
                        try:
                            structured_message = json.dumps(error_payload, ensure_ascii=False, default=str)
                        except Exception:
                            structured_message = None
                # Handle invalid field errors with field discovery suggestions
                if any(marker in lower_msg for marker in invalid_field_markers):
                    # Best-effort extraction of the invalid field name between quotes
                    invalid_field_name: str | None = None
                    try:
                        text = str(fault.faultString)
                        quote_start = text.find("'")
                        quote_end = text.find("'", quote_start + 1) if quote_start != -1 else -1
                        if quote_start != -1 and quote_end != -1:
                            invalid_field_name = text[quote_start + 1 : quote_end]
                    except Exception:
                        invalid_field_name = None

                    obsolete_suggestion: str | None = None
                    if model and invalid_field_name:
                        key = f"{model}:{invalid_field_name}"
                        obsolete_suggestion = _OBSOLETE_FIELD_MAPPING.get(key)

                    field_metadata: dict[str, Any] = {}
                    available_fields_list: list[dict[str, Any]] = []
                    try:
                        if model:
                            field_metadata = self._discover_fields(models, odoo_db, uid, odoo_password, model, odoo_url)
                    except Exception:
                        field_metadata = {}

                    if field_metadata:
                        # Build a list of field descriptors and sort by relevance (required > stored > name)
                        for fname, meta in field_metadata.items():
                            available_fields_list.append(
                                {
                                    "name": fname,
                                    "type": meta.get("type"),
                                    "label": meta.get("string"),
                                    "required": bool(meta.get("required")),
                                    "store": bool(meta.get("store", True)),
                                }
                            )
                        available_fields_list.sort(
                            key=lambda f: (
                                not f["required"],
                                not f["store"],
                                (f["name"] or ""),
                            )
                        )
                        available_fields_list = available_fields_list[:50]

                    similar_suggestions: list[str] = []
                    if invalid_field_name and available_fields_list:
                        for f in available_fields_list:
                            if invalid_field_name in f["name"] or f["name"] in invalid_field_name:
                                similar_suggestions.append(f["name"])
                        similar_suggestions = sorted(set(similar_suggestions))

                    message += " | Le champ demandé n'est pas valide pour ce modèle."
                    if invalid_field_name and model:
                        message += f" Champ invalide: '{invalid_field_name}' sur le modèle '{model}'."
                    if obsolete_suggestion:
                        message += f" Ce champ semble obsolète; essayez plutôt '{obsolete_suggestion}'."

                    invalid_field_payload = {
                        "error": message,
                        "model": model,
                        "invalid_field": invalid_field_name,
                        "available_fields": available_fields_list,
                        "similar_suggestions": similar_suggestions,
                    }
                    try:
                        structured_message = json.dumps(invalid_field_payload, ensure_ascii=False, default=str)
                    except Exception:
                        # keep previous structured_message if any, otherwise leave as text
                        pass
                try:
                    tb = format_error(fault)
                    PrintStyle.error(tb)
                except Exception:
                    PrintStyle.error(message)
                raise RepairableException(structured_message or message)
            except Exception as e:
                # Preserve context: log the full formatted traceback and include exception type in the message
                try:
                    tb = format_error(e)
                    PrintStyle.error(tb)
                except Exception:
                    # Fallback minimal log if formatting fails
                    PrintStyle.error(f"{type(e).__name__}: {e}")
                raise RepairableException(f"{type(e).__name__}: {e}")

        data = None
        max_attempts = 2
        attempt = 0
        last_error: RepairableException | None = None

        while attempt < max_attempts:
            try:
                data = await asyncio.to_thread(_run)
                break
            except RepairableException as exc:
                last_error = exc
                # Try a single auto-correction pass for invalid field errors on first failure
                if attempt == 0:
                    effective_fields: list[str] | None = None
                    fields_source: str | None = None  # "root" or "options"

                    if fields:
                        effective_fields = fields
                        fields_source = "root"
                    elif isinstance(options, dict) and isinstance(options.get("fields"), list):
                        effective_fields = options.get("fields")
                        fields_source = "options"

                    if effective_fields:
                        corrected_fields = self._auto_correct_fields(model, method, effective_fields, str(exc))
                        if corrected_fields is not None:
                            try:
                                old_fields = ", ".join(effective_fields)
                            except Exception:
                                old_fields = str(effective_fields)
                            try:
                                new_fields = ", ".join(corrected_fields)
                            except Exception:
                                new_fields = str(corrected_fields)
                            try:
                                PrintStyle.hint(
                                    f"Auto-correcting Odoo fields for {model or ''}:{method or ''} from [{old_fields}] to [{new_fields}] after invalid field error."
                                )
                            except Exception:
                                # Ignore logging issues
                                pass

                            # Write corrected fields back to the original source
                            if fields_source == "root":
                                fields = corrected_fields
                            elif fields_source == "options":
                                if isinstance(options, dict):
                                    options["fields"] = corrected_fields

                            attempt += 1
                            continue
                # No correction possible or retry already attempted
                raise

        if data is None and last_error is not None:
            raise last_error

        operation = "call"
        if discover_models:
            operation = "discover_models"
        elif discover_fields:
            operation = "discover_fields"

        message = json.dumps(
            {
                "model": model,
                "method": method,
                "operation": operation,
                "result": data,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return Response(message=message, break_loop=False)

    def get_log_object(self):
        heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}'"
        if self.args:
            m = self.args.get("model")
            meth = self.args.get("method")
            if m or meth:
                heading = f"icon://construction {self.agent.agent_name}: Using tool '{self.name}' on '{m or 'unknown'}:{meth or 'unknown'}'"
        return self.agent.context.log.log(type="tool", heading=heading, content="", kvps=self.args)

    async def before_execution(self, **kwargs):
        await super().before_execution(**kwargs)
        url = getattr(self.agent.config, "odoo_url", "") or ""
        db = getattr(self.agent.config, "odoo_db", "") or ""
        PrintStyle(font_color="#85C1E9").print(f"Connecting to Odoo at {url} (db={db})")

    async def after_execution(self, response: Response, **kwargs):
        await super().after_execution(response, **kwargs)

    @staticmethod
    def _discover_models(models_proxy: xmlrpclib.ServerProxy, db: str, uid: int, password: str, url: str) -> list[dict[str, Any]]:
        cache_key = f"{url.rstrip('/')}_{db}"
        cached = OdooCall._models_cache.get(cache_key)
        if cached is not None:
            return cached

        domain = [["transient", "=", False]]
        fields = ["model", "name"]
        params = {
            "domain": domain,
            "fields": fields,
            "limit": 200,
            "order": "name asc",
        }

        result = models_proxy.execute_kw(
            db,
            uid,
            password,
            "ir.model",
            "search_read",
            [params["domain"]],
            {"fields": params["fields"], "limit": params["limit"], "order": params["order"]},
        )

        business_prefixes = ("sale.", "purchase.", "account.", "crm.", "project.", "stock.", "product.", "res.", "hr.")
        filtered: list[dict[str, Any]] = []
        for rec in result:
            model_name = rec.get("model", "") or ""
            if model_name.startswith("ir.") or model_name.startswith("base."):
                continue
            if not model_name.startswith(business_prefixes):
                continue
            filtered.append({"model": model_name, "name": rec.get("name", model_name)})

        OdooCall._models_cache[cache_key] = filtered
        return filtered

    @staticmethod
    def _discover_fields(
        models_proxy: xmlrpclib.ServerProxy,
        db: str,
        uid: int,
        password: str,
        model_name: str,
        url: str,
    ) -> dict[str, Any]:
        cache_key = f"{url.rstrip('/')}_{db}_{model_name}"
        cached = OdooCall._fields_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result: dict[str, Any] = models_proxy.execute_kw(
                db,
                uid,
                password,
                model_name,
                "fields_get",
                [[]],
                {"attributes": ["type", "string", "required", "store", "relation"]},
            )
        except Exception:
            result = {}

        # Optionally filter out internal/system fields starting with '__'
        filtered_result: dict[str, Any] = {}
        for fname, meta in (result or {}).items():
            if fname.startswith("__"):
                continue
            filtered_result[fname] = meta

        OdooCall._fields_cache[cache_key] = filtered_result
        return filtered_result

    @staticmethod
    def _auto_correct_fields(
        model: str | None,
        method: str | None,
        fields: list[str] | None,
        error_message: str,
    ) -> list[str] | None:
        """Attempt to auto-correct invalid fields based on structured error payload.

        Expects error_message to be either plain text or a JSON string with keys like
        'invalid_field' and 'similar_suggestions'. Returns a new fields list or None
        if no safe correction can be inferred.
        """
        if not fields or not isinstance(fields, list):
            return None

        payload: dict[str, Any] | None = None
        try:
            payload_candidate = json.loads(error_message)
            if isinstance(payload_candidate, dict):
                payload = payload_candidate
        except Exception:
            payload = None

        if not payload:
            return None

        invalid_field = payload.get("invalid_field")
        similar_suggestions = payload.get("similar_suggestions") or []
        if not isinstance(similar_suggestions, list):
            similar_suggestions = []

        replacement: str | None = None
        if model and invalid_field:
            key = f"{model}:{invalid_field}"
            replacement = _OBSOLETE_FIELD_MAPPING.get(key)

        # Fallback: if exactly one similar suggestion, use it
        if not replacement and similar_suggestions:
            unique = list({str(s) for s in similar_suggestions if isinstance(s, str)})
            if len(unique) == 1:
                replacement = unique[0]

        if not invalid_field or not replacement:
            return None

        # Only auto-correct when the invalid field is explicitly present in the fields list
        if invalid_field not in fields:
            return None

        corrected = [replacement if f == invalid_field else f for f in fields]
        return corrected
