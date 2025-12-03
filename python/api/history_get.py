from python.helpers.api import ApiHandler, Request, Response
from flask import session
from python.helpers import user_management


class GetHistory(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        ctxid = input.get("context", [])
        context = self.get_context(ctxid)
        # Enforce ownership for non-admin users
        username = session.get('username')
        role = session.get('role')
        if role != user_management.ROLE_ADMIN:
            owner = getattr(context, 'metadata', {}).get('owner') if hasattr(context, 'metadata') else None
            if owner != username:
                return Response("Access denied to this chat", 403)
        agent = context.streaming_agent or context.agent0
        history = agent.history.output_text()
        size = agent.history.get_tokens()

        return {
            "history": history,
            "tokens": size
        }