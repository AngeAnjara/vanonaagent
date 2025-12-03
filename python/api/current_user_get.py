from python.helpers.api import ApiHandler, Request, Response
from flask import session


class CurrentUserGet(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        return {
            "success": True,
            "user": {
                "username": session.get("username"),
                "role": session.get("role"),
                "user_id": session.get("user_id"),
            },
        }
