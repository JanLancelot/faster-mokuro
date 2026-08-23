import json
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


class InvalidImage(Exception):
    def __init__(self, message="Corrupted file or unsupported type"):
        super().__init__(message)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        return json.JSONEncoder.default(self, obj)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, cls=NumpyEncoder)


def imread(path):
    """Read an image as a BGR array. Animated images decode to their first frame."""
    try:
        with Image.open(path) as img:
            return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise  # not a decoding problem
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise InvalidImage(f"{path}: {e}") from e


def get_path_format(path: Path):
    if path.is_dir():
        return ""
    else:
        return path.suffix.lower()


def unzip(path_src: Path, path_dst: Path, correct_duplicated_root=True):
    with zipfile.ZipFile(path_src, "r") as zip_ref:
        zip_ref.extractall(path_dst)

    if correct_duplicated_root:
        # check if there's only one directory in the extracted directory and it has the same name as the archive
        extracted_content = list(path_dst.iterdir())
        if len(extracted_content) == 1:
            extracted_dir = extracted_content[0]
            if extracted_dir.is_dir():
                archive_name = path_src.stem  # remove extension
                if archive_name == extracted_dir.name:
                    for item in extracted_dir.iterdir():
                        shutil.move(str(item), str(path_dst))
                    extracted_dir.rmdir()


def embed_mokuro_in_archive(archive_path: Path, mokuro_path: Path):
    """
    Embed the .mokuro metadata directly into a .cbz / .zip archive.
    Writes both the named .mokuro file and index.mokuro for maximum reader compatibility.
    """
    if not archive_path.is_file() or not mokuro_path.is_file():
        return

    mokuro_bytes = mokuro_path.read_bytes()
    mokuro_name = mokuro_path.name

    with zipfile.ZipFile(archive_path, "a") as zf:
        existing_names = set(zf.namelist())
        if mokuro_name not in existing_names:
            zf.writestr(mokuro_name, mokuro_bytes)
        if "index.mokuro" not in existing_names and mokuro_name != "index.mokuro":
            zf.writestr("index.mokuro", mokuro_bytes)


def bundle_to_cbz(dir_path: Path, mokuro_path: Path, dst_path: Path = None) -> Path:
    """
    Bundle a manga directory and its .mokuro metadata into a single self-contained .cbz archive.
    """
    if dst_path is None:
        dst_path = dir_path.with_suffix(".cbz")

    from natsort import natsorted

    with zipfile.ZipFile(dst_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f_path in natsorted(dir_path.rglob("*")):
            if f_path.is_file() and f_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".avif"):
                rel = f_path.relative_to(dir_path)
                zf.write(f_path, rel)

        if mokuro_path.is_file():
            mokuro_bytes = mokuro_path.read_bytes()
            zf.writestr(mokuro_path.name, mokuro_bytes)
            if mokuro_path.name != "index.mokuro":
                zf.writestr("index.mokuro", mokuro_bytes)

    return dst_path
