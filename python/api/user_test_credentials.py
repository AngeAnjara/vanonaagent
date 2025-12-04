from python.helpers.api import ApiHandler, Request, Response
from python.helpers import user_management


class UserTestCredentials(ApiHandler):
    @classmethod
    def requires_admin(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request):
        try:
            username = (input.get("username") or "").strip()
            password = input.get("password") or ""
            if not username or not password:
                return Response(
                    response="username and password are required",
                    status=400,
                    mimetype="text/plain",
                )

            user = user_management.authenticate_user(username, password)
            if user:
                return {
                    "success": True,
                    "message": "Identifiants valides",
                    "user": {
                        "id": user.get("id"),
                        "username": user.get("username"),
                        "role": user.get("role"),
                    },
                }
            else:
                return {"success": False, "message": "Identifiants invalides"}
        except Exception as e:
            return Response(response=str(e), status=400, mimetype="text/plain")
