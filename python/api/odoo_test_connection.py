from xmlrpc import client as xmlrpclib

from python.helpers.api import ApiHandler, Request, Response
from python.helpers import settings
from python.helpers.errors import format_error
from python.helpers.print_style import PrintStyle


class OdooTestConnection(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Test connection to Odoo using current settings and optional overrides.

        Expects JSON body with optional keys: url, db, user.
        Password is always taken from secure settings / dotenv.
        """
        try:
            current = settings.get_settings()

            url = input.get("url") or current.get("odoo_url", "")
            db = input.get("db") or current.get("odoo_db", "")
            user = input.get("user") or current.get("odoo_user", "")
            password = current.get("odoo_password", "")

            missing = [
                name
                for name, value in {
                    "ODOO_URL": url,
                    "ODOO_DB": db,
                    "ODOO_USER": user,
                    "ODOO_PASSWORD": password,
                }.items()
                if not value
            ]
            if missing:
                return {
                    "success": False,
                    "message": (
                        f"Missing Odoo configuration: {', '.join(missing)}. "
                        "Please configure these in Settings > Odoo Integration."
                    ),
                }

            common_url = f"{url.rstrip('/')}/xmlrpc/2/common"
            object_url = f"{url.rstrip('/')}/xmlrpc/2/object"

            common = xmlrpclib.ServerProxy(common_url)
            uid = common.authenticate(db, user, password, {})

            if not uid:
                return {
                    "success": False,
                    "message": (
                        "Authentication to Odoo failed. "
                        "Please verify your username, password, and database name in Settings > Odoo Integration."
                    ),
                }

            version_info = {}
            try:
                version_info = common.version() or {}
            except Exception:  # noqa: BLE001
                version_info = {}

            odoo_version = version_info.get("server_version", "") or ""

            available_models = []
            enrichment_hint = ""
            try:
                models_proxy = xmlrpclib.ServerProxy(object_url)
                domain = [["transient", "=", False]]
                fields = ["model", "name"]
                result = models_proxy.execute_kw(
                    db,
                    uid,
                    password,
                    "ir.model",
                    "search_read",
                    [domain],
                    {"fields": fields, "limit": 500, "order": "name asc"},
                )

                result_by_model = {rec.get("model"): rec for rec in result}
                common_business_models = [
                    "sale.order",
                    "sale.order.line",
                    "purchase.order",
                    "account.move",
                    "account.move.line",
                    "account.payment",
                    "res.partner",
                    "product.product",
                    "product.template",
                    "stock.picking",
                    "stock.move",
                    "crm.lead",
                    "project.project",
                    "project.task",
                    "hr.employee",
                    "hr.leave",
                ]

                for model_name in common_business_models:
                    rec = result_by_model.get(model_name)
                    available_models.append(
                        {
                            "model": model_name,
                            "name": (rec or {}).get("name", model_name),
                            "available": rec is not None,
                        }
                    )

            except Exception as enrich_err:  # noqa: BLE001
                try:
                    tb = format_error(enrich_err)
                    PrintStyle.error(tb)
                except Exception:  # noqa: BLE001
                    PrintStyle.error(f"{type(enrich_err).__name__}: {enrich_err}")
                enrichment_hint = " However, Agent Zero could not retrieve the list of business models (missing access rights to ir.model or another server-side issue)."

            return {
                "success": True,
                "message": "Odoo connection and authentication successful." + enrichment_hint,
                "available_models": available_models,
                "odoo_version": odoo_version,
            }

        except Exception as e:  # noqa: BLE001
            try:
                tb = format_error(e)
                PrintStyle.error(tb)
            except Exception:  # noqa: BLE001
                PrintStyle.error(f"{type(e).__name__}: {e}")

            base_message = f"Error testing Odoo connection: {type(e).__name__}: {e}"
            hint = ""
            text = str(e).lower()
            if "connection refused" in text or "timed out" in text or "timeout" in text:
                hint = " Please check that your Odoo URL is correct and the server is reachable from Agent Zero."

            return {
                "success": False,
                "message": base_message + hint,
            }
