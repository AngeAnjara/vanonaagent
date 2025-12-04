from python.helpers.api import ApiHandler, Request, Response
from python.helpers import persist_chat


class UserChatDeleteApi(ApiHandler):
    @classmethod
    def requires_admin(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request):
        chat_id = (input.get("id") or "").strip()
        if not chat_id:
            return Response(response="Missing chat id", status=400, mimetype="text/plain")
        try:
            persist_chat.remove_msg_files(chat_id)
            persist_chat.remove_chat(chat_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
