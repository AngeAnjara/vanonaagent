from datetime import datetime
from python.helpers.api import ApiHandler, Request, Response
from python.helpers import user_management, persist_chat
from agent import AgentContext, AgentContextType


class UserChatsApi(ApiHandler):
    @classmethod
    def requires_admin(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request):
        try:
            username = (input.get("username") or "").strip()
            if not username:
                return Response(response="Username manquant", status=400, mimetype="text/plain")

            user = user_management.get_user_by_username(username)
            if not user:
                return {"success": False, "error": "Utilisateur introuvable"}

            # Load chats for this user (also migrates/initializes as needed)
            ctxids = persist_chat.load_tmp_chats(username)

            chats = []
            for ctxid in ctxids:
                ctx = AgentContext.get(ctxid)
                if not ctx:
                    continue
                # Extract fields safely
                created_at = ctx.created_at.isoformat() if getattr(ctx, "created_at", None) else None
                last_message = ctx.last_message.isoformat() if getattr(ctx, "last_message", None) else None
                ctype = ctx.type.value if getattr(ctx, "type", None) else AgentContextType.USER.value
                owner = None
                if hasattr(ctx, "metadata") and isinstance(ctx.metadata, dict):
                    owner = ctx.metadata.get("owner")

                chats.append(
                    {
                        "id": ctx.id,
                        "name": ctx.name,
                        "type": ctype,
                        "created_at": created_at,
                        "last_message": last_message,
                        "owner": owner,
                    }
                )

            # Sort by last_message desc (fallback to created_at)
            def sort_key(item: dict):
                ts = item.get("last_message") or item.get("created_at")
                try:
                    return datetime.fromisoformat(ts) if ts else datetime.fromtimestamp(0)
                except Exception:
                    return datetime.fromtimestamp(0)

            chats.sort(key=sort_key, reverse=True)

            return {"success": True, "username": username, "total": len(chats), "chats": chats}
        except Exception as e:
            return {"success": False, "error": str(e)}
