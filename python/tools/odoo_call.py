import asyncio
import json
from typing import Any
from xmlrpc import client as xmlrpclib

from python.helpers.tool import Tool, Response
from python.helpers.errors import RepairableException, format_error
from python.helpers.print_style import PrintStyle


class OdooCall(Tool):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.odoo_url: str | None = "http://188.166.107.40:9090"
        self.odoo_db: str | None = "production"
        self.odoo_user: str | None = "admin"
        self.odoo_password: str | None = "admin"

    async def execute(self, **kwargs) -> Response:
        # Prefer kwargs (if provided) to align with potential external callers, fallback to self.args
        model: str | None = kwargs.get("model", self.args.get("model"))
        method: str | None = kwargs.get("method", self.args.get("method"))
        domain: Any = kwargs.get("domain", self.args.get("domain", []))
        fields: list[str] | None = kwargs.get("fields", self.args.get("fields"))
        options: dict[str, Any] = kwargs.get("options", self.args.get("options", {}))
        ids = kwargs.get("ids", self.args.get("ids"))
        vals = kwargs.get("vals", self.args.get("vals"))
        raw_args = kwargs.get("raw_args", self.args.get("raw_args", []))

        # Validate configuration
        missing = [
            k for k, v in {
                "ODOO_URL": self.odoo_url,
                "ODOO_DB": self.odoo_db,
                "ODOO_USER": self.odoo_user,
                "ODOO_PASSWORD": self.odoo_password,
            }.items() if not v
        ]
        if missing:
            raise RepairableException(
                f"Missing Odoo configuration values in .env: {', '.join(missing)}"
            )
        if not model or not method:
            raise RepairableException("'model' and 'method' are required arguments for odoo_call")

        # Build endpoints
        common_url = f"{self.odoo_url.rstrip('/')}/xmlrpc/2/common"
        object_url = f"{self.odoo_url.rstrip('/')}/xmlrpc/2/object"

        # Prepare execution in thread to avoid blocking
        def _run() -> Any:
            try:
                common = xmlrpclib.ServerProxy(common_url)
                uid = common.authenticate(self.odoo_db, self.odoo_user, self.odoo_password, {})
                if not uid:
                    raise RepairableException("Authentication to Odoo failed. Check ODOO_USER/ODOO_PASSWORD.")

                models = xmlrpclib.ServerProxy(object_url)

                args_list = []
                if method in ("search", "search_read", "read_group"):
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
                else:
                    # generic: allow passing raw 'args' list
                    if not isinstance(raw_args, list):
                        raise RepairableException("'raw_args' must be a list when using generic method")
                    args_list = raw_args

                kwargs_call: dict[str, Any] = {}
                if fields and method in ("search_read", "read"):
                    kwargs_call["fields"] = fields
                if options and isinstance(options, dict):
                    kwargs_call.update(options)

                result = models.execute_kw(
                    self.odoo_db,
                    uid,
                    self.odoo_password,
                    model,
                    method,
                    args_list,
                    kwargs_call,
                )
                return result
            except RepairableException:
                raise
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
        PrintStyle(font_color="#85C1E9").print(f"Connecting to Odoo at {self.odoo_url} (db={self.odoo_db})")

    async def after_execution(self, response: Response, **kwargs):
        await super().after_execution(response, **kwargs)
