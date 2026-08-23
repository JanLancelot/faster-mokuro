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


def test_embed_mokuro_in_archive():
    import zipfile
    from mokuro.utils import embed_mokuro_in_archive

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_path = tmp_path / "test.cbz"
        mokuro_path = tmp_path / "test.mokuro"

        # Create a sample cbz
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("001.jpg", b"fake_image_data")

        mokuro_path.write_text('{"title": "Test", "pages": []}', encoding="utf-8")

        embed_mokuro_in_archive(zip_path, mokuro_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "test.mokuro" in namelist
            assert "index.mokuro" in namelist
            assert zf.read("test.mokuro") == b'{"title": "Test", "pages": []}'


def test_bundle_to_cbz():
    import zipfile
    from mokuro.utils import bundle_to_cbz

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        vol_dir = tmp_path / "vol1"
        vol_dir.mkdir()
        (vol_dir / "001.jpg").write_bytes(b"image1")
        (vol_dir / "002.png").write_bytes(b"image2")
        (vol_dir / "ignore.txt").write_bytes(b"ignore")

        mokuro_path = tmp_path / "vol1.mokuro"
        mokuro_path.write_text('{"volume": "vol1"}', encoding="utf-8")

        cbz_out = bundle_to_cbz(vol_dir, mokuro_path)
        assert cbz_out.is_file()
        assert cbz_out.suffix == ".cbz"

        with zipfile.ZipFile(cbz_out, "r") as zf:
            namelist = zf.namelist()
            assert "001.jpg" in namelist
            assert "002.png" in namelist
            assert "ignore.txt" not in namelist
            assert "vol1.mokuro" in namelist
            assert "index.mokuro" in namelist


def test_cleanup_volume_mess():
    from mokuro.run import _cleanup_volume_mess
    from mokuro.volume import Volume

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        vol_dir = tmp_path / "vol1"
        vol_dir.mkdir()
        (vol_dir / "001.jpg").write_bytes(b"image")

        mokuro_file = tmp_path / "vol1.mokuro"
        mokuro_file.write_text('{"pages": []}', encoding="utf-8")

        ocr_cache_dir = tmp_path / "_ocr" / "vol1"
        ocr_cache_dir.mkdir(parents=True)
        (ocr_cache_dir / "001.json").write_text('{}', encoding="utf-8")

        volume = Volume(vol_dir)

        # Run mess cleanup with remove_source_dir=True
        _cleanup_volume_mess(volume, remove_source_dir=True)

        assert not mokuro_file.exists()
        assert not ocr_cache_dir.exists()
        assert not (tmp_path / "_ocr").exists()
        assert not vol_dir.exists()

