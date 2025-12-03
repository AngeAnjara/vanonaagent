from python.helpers.api import ApiHandler, Request, Response
from flask import session
from python.helpers import user_management


class UserManagementApi(ApiHandler):
    @classmethod
    def requires_admin(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        action = input.get("action")
        if not action:
            return Response("Action manquante", 400)

        try:
            if action == "list":
                return {"success": True, "users": user_management.get_all_users()}

            if action == "get_current":
                return {
                    "success": True,
                    "user": {
                        "username": session.get("username"),
                        "role": session.get("role"),
                        "user_id": session.get("user_id"),
                    },
                }

            if action == "create":
                username = input.get("username", "").strip()
                password = input.get("password", "")
                role = input.get("role", user_management.ROLE_USER)
                created_by = session.get("username", "system")
                user = user_management.create_user(username, password, role, created_by)
                return {"success": True, "user": user}

            if action == "update":
                user_id = int(input.get("id"))
                role = input.get("role")
                password = input.get("password")
                user = user_management.update_user(user_id, role=role, password=password)
                return {"success": True, "user": user}

            if action == "delete":
                user_id = int(input.get("id"))
                # prevent deleting self
                if session.get("user_id") == user_id:
                    return Response("Vous ne pouvez pas supprimer votre propre utilisateur", 400)
                user_management.delete_user(user_id)
                return {"success": True}

            return Response(f"Action inconnue: {action}", 400)
        except Exception as e:
            return {"success": False, "error": str(e)}
