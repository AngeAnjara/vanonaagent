import asyncio
import json
from typing import Any
from xmlrpc import client as xmlrpclib

from python.helpers.tool import Tool, Response
from python.helpers.errors import RepairableException, format_error
from python.helpers.print_style import PrintStyle


class OdooCall(Tool):

    _models_cache: dict[str, list[dict[str, Any]]] = {}

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
        if not discover_models and (not model or not method):
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
                structured_message: str | None = None
                suggested_models: list[dict[str, Any]] = []
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

        data = await asyncio.to_thread(_run)

        message = json.dumps(
            {
                "model": model,
                "method": method,
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
