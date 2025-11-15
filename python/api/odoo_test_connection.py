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
                        "Missing Odoo configuration values. "
                        "Please configure Odoo in Settings > Odoo Integration."
                    ),
                }

            common_url = f"{url.rstrip('/')}/xmlrpc/2/common"

            common = xmlrpclib.ServerProxy(common_url)
            uid = common.authenticate(db, user, password, {})

            if not uid:
                return {
                    "success": False,
                    "message": "Authentication to Odoo failed. Check username/password and database.",
                }

            return {"success": True, "message": "Odoo connection and authentication successful."}

        except Exception as e:  # noqa: BLE001
            try:
                tb = format_error(e)
                PrintStyle.error(tb)
            except Exception:  # noqa: BLE001
                PrintStyle.error(f"{type(e).__name__}: {e}")

            return {
                "success": False,
                "message": f"Error testing Odoo connection: {type(e).__name__}: {e}",
            }
