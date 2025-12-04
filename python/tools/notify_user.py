from python.helpers.tool import Tool, Response
from agent import AgentContext
from python.helpers.notification import NotificationPriority, NotificationType
from python.helpers import files
from flask import session
import json

class NotifyUserTool(Tool):

    async def execute(self, **kwargs):

        message = self.args.get("message", "")
        title = self.args.get("title", "")
        detail = self.args.get("detail", "")
        notification_type = self.args.get("type", NotificationType.INFO)
        priority = self.args.get("priority", NotificationPriority.HIGH) # by default, agents should notify with high priority
        timeout = int(self.args.get("timeout", 30)) # agent's notifications should have longer timeouts

        try:
            notification_type = NotificationType(notification_type)
        except ValueError:
            return Response(message=f"Invalid notification type: {notification_type}", break_loop=False)

        try:
            priority = NotificationPriority(priority)
        except ValueError:
            return Response(message=f"Invalid notification priority: {priority}", break_loop=False)

        if not message:
            return Response(message="Message is required", break_loop=False)

        # Resolve target user
        current_user = session.get("username")
        role = session.get("role")
        target_user = self.args.get("target_user", None)

        if target_user and target_user != current_user and role != "admin":
            return Response(message="Permission refusée: seuls les admins peuvent notifier un autre utilisateur", break_loop=False)

        target = target_user or current_user

        # Store per-user notification
        try:
            notif = {
                "title": title,
                "message": message,
                "detail": detail,
                "type": notification_type.value if isinstance(notification_type, NotificationType) else str(notification_type),
                "priority": priority.value if isinstance(priority, NotificationPriority) else int(priority),
                "display_time": timeout,
            }
            path = files.get_abs_path("tmp/notifications")
            files.make_dirs(path)
            user_file = files.get_abs_path(path, f"{target}.json")
            existing = []
            if files.exists(user_file):
                try:
                    existing = json.loads(files.read_file(user_file)) or []
                except Exception:
                    existing = []
            existing.append(notif)
            files.write_file(user_file, json.dumps(existing, ensure_ascii=False))
        except Exception:
            # ignore storage errors and proceed
            pass

        # Back-compat: also add to global manager for active session visibility
        AgentContext.get_notification_manager().add_notification(
            message=message,
            title=title,
            detail=detail,
            type=notification_type,
            priority=priority,
            display_time=timeout,
        )
        return Response(message=self.agent.read_prompt("fw.notify_user.notification_sent.md"), break_loop=False)
