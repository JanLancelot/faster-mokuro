import platform
import subprocess
import sys
from loguru import logger


def send_notification(title: str, message: str, sound: bool = True) -> bool:
    """
    Send a native desktop notification.

    Args:
        title: Notification title.
        message: Notification body text.
        sound: Whether to play a notification sound.

    Returns:
        True if the notification command executed successfully, False otherwise.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            sound_clause = 'sound name "Glass"' if sound else ""
            # Escape backslashes and double quotes for AppleScript
            escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
            escaped_msg = message.replace("\\", "\\\\").replace('"', '\\"')
            script = f'display notification "{escaped_msg}" with title "{escaped_title}" {sound_clause}'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=5)
            return True

        elif system == "Windows":
            # PowerShell toast notification for Windows 10/11
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
            $textNodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Mokuro")
            $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
            $notifier.Show($notification)
            """
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True

        elif system == "Linux":
            cmd = ["notify-send", title, message]
            if sound:
                cmd.extend(["-u", "normal"])
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
            return True

    except Exception as e:
        logger.debug(f"Failed to send desktop notification ({system}): {e}")

    return False
