import os
import platform
import plistlib
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Union

from loguru import logger

from mokuro.notify import send_notification


SERVICE_NAME = "Process with Mokuro"
WORKFLOW_NAME = f"{SERVICE_NAME}.workflow"


def _get_python_command(custom_python: Optional[str] = None) -> str:
    """Resolve the Python executable to run mokuro in shortcut actions."""
    if custom_python:
        return custom_python

    # Prefer sys.executable if it's valid and contains mokuro
    if sys.executable and Path(sys.executable).is_file():
        return sys.executable

    # Fall back to 'mokuro' on PATH or 'python3'
    mokuro_bin = shutil.which("mokuro")
    if mokuro_bin:
        return mokuro_bin

    return "python3"


# ============================================================================
# macOS Quick Action (Finder Service)
# ============================================================================

def _get_macos_services_dir() -> Path:
    return Path.home() / "Library" / "Services"


def _build_macos_workflow(workflow_dir: Path, python_cmd: str):
    contents_dir = workflow_dir / "Contents"
    contents_dir.mkdir(parents=True, exist_ok=True)

    info_plist = {
        "NSIconPath": "",
        "NSServices": [
            {
                "NSBackgroundColorName": "background",
                "NSBackgroundMode": 1,
                "NSMenuItem": {
                    "default": SERVICE_NAME,
                },
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {
                    "NSApplicationIdentifier": "com.apple.finder",
                },
                "NSSendFileTypes": [
                    "public.item",
                    "public.folder",
                ],
            }
        ],
    }

    info_plist_path = contents_dir / "Info.plist"
    with open(info_plist_path, "wb") as f:
        plistlib.dump(info_plist, f)

    # Automator script executed when user clicks the Quick Action
    # Set standard PATH so tools like python / osascript resolve properly
    shell_script = (
        'export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"\n'
        f'"{python_cmd}" -m mokuro.integration run "$@"\n'
    )

    doc_wflow = {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.path"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": shell_script,
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,  # 1 = pass input as arguments ($@)
                        "shell": "/bin/zsh",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                }
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
        },
    }

    doc_wflow_path = contents_dir / "document.wflow"
    with open(doc_wflow_path, "wb") as f:
        plistlib.dump(doc_wflow, f)


def install_macos_shortcut(python_cmd: Optional[str] = None) -> Path:
    python_cmd = _get_python_command(python_cmd)
    services_dir = _get_macos_services_dir()
    workflow_dir = services_dir / WORKFLOW_NAME

    if workflow_dir.exists():
        shutil.rmtree(workflow_dir)

    _build_macos_workflow(workflow_dir, python_cmd)
    logger.info(f"Installed macOS Quick Action to: {workflow_dir}")
    return workflow_dir


def uninstall_macos_shortcut() -> bool:
    services_dir = _get_macos_services_dir()
    workflow_dir = services_dir / WORKFLOW_NAME

    if workflow_dir.exists():
        shutil.rmtree(workflow_dir)
        logger.info(f"Removed macOS Quick Action: {workflow_dir}")
        return True

    logger.info("macOS Quick Action was not installed.")
    return False


# ============================================================================
# Windows Context Menu (Registry)
# ============================================================================

def install_windows_shortcut(python_cmd: Optional[str] = None) -> bool:
    if platform.system() != "Windows":
        raise OSError("Windows shortcut installation is only supported on Windows.")

    import winreg

    python_cmd = _get_python_command(python_cmd)
    cmd_str = f'"{python_cmd}" -m mokuro.integration run "%1"'

    # Keys to register: Directory, Directory background, and common archive file types
    targets = [
        r"Software\Classes\Directory\shell",
        r"Software\Classes\Directory\Background\shell",
        r"Software\Classes\SystemFileAssociations\.zip\shell",
        r"Software\Classes\SystemFileAssociations\.cbz\shell",
        r"Software\Classes\SystemFileAssociations\.cbr\shell",
    ]

    for target in targets:
        try:
            key_path = f"{target}\\{SERVICE_NAME}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, SERVICE_NAME)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\command") as key:
                if "Background" in target:
                    winreg.SetValue(key, "", winreg.REG_SZ, f'"{python_cmd}" -m mokuro.integration run "%V"')
                else:
                    winreg.SetValue(key, "", winreg.REG_SZ, cmd_str)

        except Exception as e:
            logger.error(f"Failed to write registry key for {target}: {e}")
            return False

    logger.info("Installed Windows Explorer context menu shortcuts.")
    return True


def uninstall_windows_shortcut() -> bool:
    if platform.system() != "Windows":
        raise OSError("Windows shortcut uninstallation is only supported on Windows.")

    import winreg

    targets = [
        r"Software\Classes\Directory\shell",
        r"Software\Classes\Directory\Background\shell",
        r"Software\Classes\SystemFileAssociations\.zip\shell",
        r"Software\Classes\SystemFileAssociations\.cbz\shell",
        r"Software\Classes\SystemFileAssociations\.cbr\shell",
    ]

    removed_any = False
    for target in targets:
        key_path = f"{target}\\{SERVICE_NAME}"
        try:
            # Delete subkey 'command' first
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{key_path}\\command")
            except FileNotFoundError:
                pass
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            removed_any = True
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Error removing registry key {key_path}: {e}")

    logger.info("Removed Windows Explorer context menu shortcuts.")
    return removed_any


# ============================================================================
# Linux File Managers (Nautilus / Nemo / Dolphin)
# ============================================================================

def install_linux_shortcut(python_cmd: Optional[str] = None) -> List[Path]:
    python_cmd = _get_python_command(python_cmd)
    installed = []

    # Nautilus / Nemo script
    nautilus_scripts_dir = Path.home() / ".local" / "share" / "nautilus" / "scripts"
    nemo_scripts_dir = Path.home() / ".local" / "share" / "nemo" / "scripts"

    script_content = (
        "#!/usr/bin/env bash\n"
        f'"{python_cmd}" -m mokuro.integration run "$@"\n'
    )

    for s_dir in [nautilus_scripts_dir, nemo_scripts_dir]:
        s_dir.mkdir(parents=True, exist_ok=True)
        script_file = s_dir / SERVICE_NAME
        script_file.write_text(script_content)
        script_file.chmod(0o755)
        installed.append(script_file)

    logger.info(f"Installed Linux file manager shortcuts to: {installed}")
    return installed


def uninstall_linux_shortcut() -> bool:
    removed = False
    paths = [
        Path.home() / ".local" / "share" / "nautilus" / "scripts" / SERVICE_NAME,
        Path.home() / ".local" / "share" / "nemo" / "scripts" / SERVICE_NAME,
    ]
    for p in paths:
        if p.exists():
            p.unlink()
            removed = True
    return removed


# ============================================================================
# High-Level Cross-Platform API
# ============================================================================

def install_shortcuts(python_cmd: Optional[str] = None):
    """
    Install right-click context menu / Quick Action shortcuts for the current operating system.
    """
    system = platform.system()
    if system == "Darwin":
        return install_macos_shortcut(python_cmd)
    elif system == "Windows":
        return install_windows_shortcut(python_cmd)
    elif system == "Linux":
        return install_linux_shortcut(python_cmd)
    else:
        raise OSError(f"Unsupported operating system: {system}")


def uninstall_shortcuts():
    """
    Uninstall right-click context menu / Quick Action shortcuts for the current operating system.
    """
    system = platform.system()
    if system == "Darwin":
        return uninstall_macos_shortcut()
    elif system == "Windows":
        return uninstall_windows_shortcut()
    elif system == "Linux":
        return uninstall_linux_shortcut()
    else:
        raise OSError(f"Unsupported operating system: {system}")


# ============================================================================
# Action Runner (Invoked when user clicks "Process with Mokuro")
# ============================================================================

def run_with_notifications(*paths: Sequence[Union[str, Path]], **kwargs):
    """
    Execute mokuro processing with native desktop notifications on start and finish.
    """
    from mokuro.run import run

    # Flatten and normalize input paths
    cleaned_paths: List[Path] = []
    for p in paths:
        if isinstance(p, (list, tuple)):
            for sub_p in p:
                if sub_p:
                    cleaned_paths.append(Path(str(sub_p)).expanduser().resolve())
        elif p:
            cleaned_paths.append(Path(str(p)).expanduser().resolve())

    if not cleaned_paths:
        send_notification("Mokuro", "No files or folders were selected to process.")
        logger.warning("No paths provided to process.")
        return

    # Create user-friendly label for notifications
    if len(cleaned_paths) == 1:
        display_name = cleaned_paths[0].name
    else:
        display_name = f"{cleaned_paths[0].name} (+{len(cleaned_paths) - 1} more)"

    send_notification("Mokuro", f"Started processing: {display_name}", sound=False)
    logger.info(f"Processing requested via OS shortcut for: {display_name}")

    try:
        # Run with safe, non-interactive defaults
        num_successful = run(
            *cleaned_paths,
            disable_confirmation=True,
            ignore_errors=True,
            **kwargs,
        )

        if num_successful and num_successful > 0:
            send_notification(
                "Mokuro",
                f"Finished processing {display_name} successfully! (.mokuro generated)",
                sound=True,
            )
        else:
            send_notification(
                "Mokuro",
                f"Completed processing {display_name}.",
                sound=True,
            )

    except Exception as e:
        logger.exception(f"Error processing {display_name}")
        send_notification(
            "Mokuro Error",
            f"Failed to process {display_name}: {e}",
            sound=True,
        )
        raise e


if __name__ == "__main__":
    import fire

    fire.Fire({
        "install": install_shortcuts,
        "uninstall": uninstall_shortcuts,
        "run": run_with_notifications,
    })
