import os
import platform
import plistlib
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mokuro.integration import (
    SERVICE_NAME,
    WORKFLOW_NAME,
    _build_macos_workflow,
    _get_python_command,
    install_macos_shortcut,
    install_shortcuts,
    run_with_notifications,
    uninstall_macos_shortcut,
    uninstall_shortcuts,
)
from mokuro.notify import send_notification


def test_get_python_command():
    cmd = _get_python_command("/custom/bin/python")
    assert cmd == "/custom/bin/python"

    cmd_default = _get_python_command()
    assert isinstance(cmd_default, str) and len(cmd_default) > 0


def test_send_notification_mock():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        res = send_notification("Test Title", "Test Message")
        assert res is True
        assert mock_run.called


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS specific test")
def test_macos_workflow_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        workflow_dir = Path(tmp_dir) / WORKFLOW_NAME
        _build_macos_workflow(workflow_dir, "/usr/bin/python3")

        info_plist_path = workflow_dir / "Contents" / "Info.plist"
        doc_wflow_path = workflow_dir / "Contents" / "document.wflow"

        assert info_plist_path.is_file()
        assert doc_wflow_path.is_file()

        # Validate with plistlib
        with open(info_plist_path, "rb") as f:
            info_plist = plistlib.load(f)
            assert info_plist["NSServices"][0]["NSMenuItem"]["default"] == SERVICE_NAME

        with open(doc_wflow_path, "rb") as f:
            doc_wflow = plistlib.load(f)
            assert doc_wflow["actions"][0]["action"]["BundleIdentifier"] == "com.apple.RunShellScript"

        # Validate with macOS plutil
        res_info = subprocess.run(["plutil", "-lint", str(info_plist_path)], capture_output=True)
        assert res_info.returncode == 0

        res_wflow = subprocess.run(["plutil", "-lint", str(doc_wflow_path)], capture_output=True)
        assert res_wflow.returncode == 0


def test_macos_install_uninstall_workflow():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("mokuro.integration._get_macos_services_dir", return_value=Path(tmp_dir)):
            wf_path = install_macos_shortcut("/usr/bin/python3")
            assert wf_path.exists()
            assert (wf_path / "Contents" / "Info.plist").exists()

            uninstalled = uninstall_macos_shortcut()
            assert uninstalled is True
            assert not wf_path.exists()

            # Second uninstall should return False
            assert uninstall_macos_shortcut() is False


def test_run_with_notifications_empty():
    with patch("mokuro.integration.send_notification") as mock_notify:
        run_with_notifications()
        assert mock_notify.called
        assert "No files" in mock_notify.call_args[0][1]


def test_run_with_notifications_success():
    with patch("mokuro.run.run", return_value=1) as mock_run, patch(
        "mokuro.integration.send_notification"
    ) as mock_notify:
        run_with_notifications("/fake/path/vol1")
        assert mock_run.called
        assert mock_notify.call_count == 2
        assert "Started" in mock_notify.call_args_list[0][0][1]
        assert "Finished" in mock_notify.call_args_list[1][0][1]


def test_run_with_notifications_error():
    with patch("mokuro.run.run", side_effect=RuntimeError("Test failure")), patch(
        "mokuro.integration.send_notification"
    ) as mock_notify:
        with pytest.raises(RuntimeError):
            run_with_notifications("/fake/path/vol1")
        assert mock_notify.call_count == 2
        assert "Failed" in mock_notify.call_args_list[1][0][1]
