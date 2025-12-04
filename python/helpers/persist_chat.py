from collections import OrderedDict
from datetime import datetime
from typing import Any
import uuid
from agent import Agent, AgentConfig, AgentContext, AgentContextType
from python.helpers import files, history
import json
from initialize import initialize_agent

from python.helpers.log import Log, LogItem

CHATS_FOLDER = "tmp/chats"
LOG_SIZE = 1000
CHAT_FILE_NAME = "chat.json"


def get_user_chats_folder(username: str):
    return files.get_abs_path(CHATS_FOLDER, username)


def get_chat_folder_path_for_user(ctxid: str, username: str):
    return files.get_abs_path(get_user_chats_folder(username), ctxid)


def get_chat_folder_path(ctxid: str, username: str | None = None):
    """
    Get the folder path for any context (chat or task).

    Args:
        ctxid: The context ID

    Returns:
        The absolute path to the context folder
    """
    if username:
        return get_chat_folder_path_for_user(ctxid, username)
    return files.get_abs_path(CHATS_FOLDER, ctxid)

def get_chat_msg_files_folder(ctxid: str, username: str | None = None):
    return files.get_abs_path(get_chat_folder_path(ctxid, username), "messages")

def save_tmp_chat(context: AgentContext, username: str | None = None):
    """Save context to the chats folder"""
    # Skip saving BACKGROUND contexts as they should be ephemeral
    if context.type == AgentContextType.BACKGROUND:
        return

    # Ensure metadata and owner
    if not hasattr(context, "metadata"):
        context.metadata = {}
    if username:
        context.metadata["owner"] = username
    owner = context.metadata.get("owner") if hasattr(context, "metadata") else None

    path = _get_chat_file_path(context.id, owner)
    files.make_dirs(path)
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    files.write_file(path, js)


def save_tmp_chats():
    """Save all contexts to the chats folder"""
    for _, context in AgentContext._contexts.items():
        # Skip BACKGROUND contexts as they should be ephemeral
        if context.type == AgentContextType.BACKGROUND:
            continue
        owner = getattr(context, "metadata", {}).get("owner", None) if hasattr(context, "metadata") else None
        save_tmp_chat(context, owner)


def unload_user_chats(username: str | None = None):
    """Remove contexts belonging to a specific user from memory."""
    if username is None:
        return  # do not unload all chats by default
    from agent import AgentContext
    to_remove: list[str] = []
    for ctx_id, ctx in list(AgentContext._contexts.items()):
        owner = getattr(ctx, "metadata", {}).get("owner") if hasattr(ctx, "metadata") else None
        if owner == username:
            to_remove.append(ctx_id)
    for ctx_id in to_remove:
        try:
            del AgentContext._contexts[ctx_id]
        except Exception:
            pass
    print(f"Unloaded {len(to_remove)} chats for user {username}")


def unload_all_chats():
    """Remove all non-BACKGROUND contexts from memory for strict per-user isolation."""
    from agent import AgentContext, AgentContextType
    to_remove: list[str] = []
    for ctx_id, ctx in list(AgentContext._contexts.items()):
        if getattr(ctx, "type", None) == AgentContextType.BACKGROUND:
            continue
        to_remove.append(ctx_id)
    for ctx_id in to_remove:
        try:
            del AgentContext._contexts[ctx_id]
        except Exception:
            pass
    print(f"Unloaded {len(to_remove)} contexts (non-BACKGROUND)")


def load_tmp_chats(username: str | None = None, reload: bool = False):
    """Load contexts from the chats folder; if username is provided, only that user's chats, else all.
    If reload=True, unload existing contexts for that user first.

    Ownership behavior:
    - When loading, we restore metadata.owner from persisted JSON if present. For any legacy chats
      lacking owner metadata, they remain admin-visible-only (stored under admin namespace after
      migration). This ensures regular users never see orphaned/legacy chats.
    - Optional future enhancement: upon first login on legacy systems, admins may reassign orphaned
      chats via the Users Dashboard.
    """
    if reload:
        unload_user_chats(username)
    _convert_v080_chats()
    _migrate_legacy_chats()

    json_files: list[str] = []
    if username:
        user_dir = get_user_chats_folder(username)
        folders = files.list_files(user_dir, "*")
        for folder_name in folders:
            json_files.append(_get_chat_file_path(folder_name, username))
    else:
        # admin/global: iterate all user subfolders
        users = files.list_files(CHATS_FOLDER, "*")
        for user in users:
            user_dir = get_user_chats_folder(user)
            folders = files.list_files(user_dir, "*")
            for folder_name in folders:
                json_files.append(_get_chat_file_path(folder_name, user))

    ctxids: list[str] = []
    for file in json_files:
        try:
            js = files.read_file(file)
            data = json.loads(js)
            ctx = _deserialize_context(data)
            # restore owner metadata from file if present
            owner = data.get("metadata", {}).get("owner") if isinstance(data.get("metadata"), dict) else None
            if owner:
                if not hasattr(ctx, "metadata"):
                    ctx.metadata = {}
                ctx.metadata["owner"] = owner
            # Security: if loading for a specific username, skip mismatched owners
            if username and owner and owner != username:
                print(f"Skipping context {ctx.id} for user {username}: owned by {owner}")
                continue
            ctxids.append(ctx.id)
        except Exception as e:
            print(f"Error loading chat {file}: {e}")
    return ctxids


def _get_chat_file_path(ctxid: str, username: str | None = None):
    if username:
        return files.get_abs_path(get_chat_folder_path_for_user(ctxid, username), CHAT_FILE_NAME)
    return files.get_abs_path(CHATS_FOLDER, ctxid, CHAT_FILE_NAME)


def _convert_v080_chats():
    json_files = files.list_files(CHATS_FOLDER, "*.json")
    for file in json_files:
        path = files.get_abs_path(CHATS_FOLDER, file)
        name = file.rstrip(".json")
        new = _get_chat_file_path(name)
        files.move_file(path, new)


def _migrate_legacy_chats():
    """
    Migrate chats stored directly under tmp/chats/<ctxid> to tmp/chats/admin/<ctxid> once.

    Notes on ownership/visibility for legacy installs:
    1) Legacy chats without explicit metadata.owner are treated as admin-owned/admin-visible by
       moving them under tmp/chats/admin. Regular users will not see these unless reassigned.
    2) Regular users will only ever see chats that carry their username in metadata.owner and
       physically reside under tmp/chats/{username}/.
    """
    # detect folders that contain chat.json directly
    entries = files.list_files(CHATS_FOLDER, "*")
    for entry in entries:
        # If entry contains a chat.json directly, move into admin namespace
        legacy_path = files.get_abs_path(CHATS_FOLDER, entry, CHAT_FILE_NAME)
        if files.exists(legacy_path):
            new_path = _get_chat_file_path(entry, "admin")
            files.make_dirs(new_path)
            files.move_file(legacy_path, new_path)
            # remove old empty dir if exists
            try:
                files.delete_dir(files.get_abs_path(CHATS_FOLDER, entry))
            except Exception:
                pass


def load_json_chats(jsons: list[str], username: str | None = None):
    """Load contexts from JSON strings"""
    ctxids = []
    for js in jsons:
        data = json.loads(js)
        if "id" in data:
            del data["id"]  # remove id to get new
        ctx = _deserialize_context(data)
        # set ownership
        if not hasattr(ctx, "metadata"):
            ctx.metadata = {}
        if username:
            ctx.metadata["owner"] = username
        ctxids.append(ctx.id)
    return ctxids


def export_json_chat(context: AgentContext):
    """Export context as JSON string"""
    data = _serialize_context(context)
    js = _safe_json_serialize(data, ensure_ascii=False)
    return js


def remove_chat(ctxid: str):
    """Remove a chat or task context across per-user folders and legacy root."""
    # Delete from legacy global path if exists
    legacy_path = get_chat_folder_path(ctxid)
    files.delete_dir(legacy_path)

    # Delete from any user subfolder
    try:
        users = files.list_files(CHATS_FOLDER, "*")
        for user in users:
            user_ctx_path = get_chat_folder_path_for_user(ctxid, user)
            files.delete_dir(user_ctx_path)
    except Exception:
        # ignore scanning errors to be robust
        pass


def remove_msg_files(ctxid: str):
    """Remove all message files for a chat or task context across per-user folders and legacy root."""
    # Legacy global messages folder
    legacy_msgs = get_chat_msg_files_folder(ctxid)
    files.delete_dir(legacy_msgs)

    # Per-user messages folders
    try:
        users = files.list_files(CHATS_FOLDER, "*")
        for user in users:
            msgs_path = get_chat_msg_files_folder(ctxid, user)
            files.delete_dir(msgs_path)
    except Exception:
        pass


def _serialize_context(context: AgentContext):
    # serialize agents
    agents = []
    agent = context.agent0
    while agent:
        agents.append(_serialize_agent(agent))
        agent = agent.data.get(Agent.DATA_NAME_SUBORDINATE, None)

    out = {
        "id": context.id,
        "name": context.name,
        "created_at": (
            context.created_at.isoformat()
            if context.created_at
            else datetime.fromtimestamp(0).isoformat()
        ),
        "type": context.type.value,
        "last_message": (
            context.last_message.isoformat()
            if context.last_message
            else datetime.fromtimestamp(0).isoformat()
        ),
        "agents": agents,
        "streaming_agent": (
            context.streaming_agent.number if context.streaming_agent else 0
        ),
        "log": _serialize_log(context.log),
    }
    # include metadata if present
    if hasattr(context, "metadata") and isinstance(context.metadata, dict):
        out["metadata"] = {k: v for k, v in context.metadata.items() if isinstance(k, str)}
    return out


def _serialize_agent(agent: Agent):
    data = {k: v for k, v in agent.data.items() if not k.startswith("_")}

    history = agent.history.serialize()

    return {
        "number": agent.number,
        "data": data,
        "history": history,
    }


def _serialize_log(log: Log):
    return {
        "guid": log.guid,
        "logs": [
            item.output() for item in log.logs[-LOG_SIZE:]
        ],  # serialize LogItem objects
        "progress": log.progress,
        "progress_no": log.progress_no,
    }


def _deserialize_context(data):
    config = initialize_agent()
    log = _deserialize_log(data.get("log", None))

    context = AgentContext(
        config=config,
        id=data.get("id", None),  # get new id
        name=data.get("name", None),
        created_at=(
            datetime.fromisoformat(
                # older chats may not have created_at - backcompat
                data.get("created_at", datetime.fromtimestamp(0).isoformat())
            )
        ),
        type=AgentContextType(data.get("type", AgentContextType.USER.value)),
        last_message=(
            datetime.fromisoformat(
                data.get("last_message", datetime.fromtimestamp(0).isoformat())
            )
        ),
        log=log,
        paused=False,
        # agent0=agent0,
        # streaming_agent=straming_agent,
    )

    agents = data.get("agents", [])
    agent0 = _deserialize_agents(agents, config, context)
    streaming_agent = agent0
    while streaming_agent and streaming_agent.number != data.get("streaming_agent", 0):
        streaming_agent = streaming_agent.data.get(Agent.DATA_NAME_SUBORDINATE, None)

    context.agent0 = agent0
    context.streaming_agent = streaming_agent

    # restore metadata if present
    md = data.get("metadata", {})
    if isinstance(md, dict):
        context.metadata = md

    return context


def _deserialize_agents(
    agents: list[dict[str, Any]], config: AgentConfig, context: AgentContext
) -> Agent:
    prev: Agent | None = None
    zero: Agent | None = None

    for ag in agents:
        current = Agent(
            number=ag["number"],
            config=config,
            context=context,
        )
        current.data = ag.get("data", {})
        current.history = history.deserialize_history(
            ag.get("history", ""), agent=current
        )
        if not zero:
            zero = current

        if prev:
            prev.set_data(Agent.DATA_NAME_SUBORDINATE, current)
            current.set_data(Agent.DATA_NAME_SUPERIOR, prev)
        prev = current

    return zero or Agent(0, config, context)


# def _deserialize_history(history: list[dict[str, Any]]):
#     result = []
#     for hist in history:
#         content = hist.get("content", "")
#         msg = (
#             HumanMessage(content=content)
#             if hist.get("type") == "human"
#             else AIMessage(content=content)
#         )
#         result.append(msg)
#     return result


def _deserialize_log(data: dict[str, Any]) -> "Log":
    log = Log()
    log.guid = data.get("guid", str(uuid.uuid4()))
    log.set_initial_progress()

    # Deserialize the list of LogItem objects
    i = 0
    for item_data in data.get("logs", []):
        log.logs.append(
            LogItem(
                log=log,  # restore the log reference
                no=i,  # item_data["no"],
                type=item_data["type"],
                heading=item_data.get("heading", ""),
                content=item_data.get("content", ""),
                kvps=OrderedDict(item_data["kvps"]) if item_data["kvps"] else None,
                temp=item_data.get("temp", False),
            )
        )
        log.updates.append(i)
        i += 1

    return log


def _safe_json_serialize(obj, **kwargs):
    def serializer(o):
        if isinstance(o, dict):
            return {k: v for k, v in o.items() if is_json_serializable(v)}
        elif isinstance(o, (list, tuple)):
            return [item for item in o if is_json_serializable(item)]
        elif is_json_serializable(o):
            return o
        else:
            return None  # Skip this property

    def is_json_serializable(item):
        try:
            json.dumps(item)
            return True
        except (TypeError, OverflowError):
            return False

    return json.dumps(obj, default=serializer, **kwargs)
