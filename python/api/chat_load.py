from python.helpers.api import ApiHandler, Input, Output, Request, Response
from flask import session


from python.helpers import persist_chat

class LoadChats(ApiHandler):
    async def process(self, input: Input, request: Request) -> Output:
        chats = input.get("chats", [])
        if not chats:
            raise Exception("No chats provided")

        ctxids = persist_chat.load_json_chats(chats, username=session.get('username'))

        return {
            "message": "Chats loaded.",
            "ctxids": ctxids,
        }
