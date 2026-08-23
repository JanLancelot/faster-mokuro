import shutil
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence, Optional, Union

import fire
from loguru import logger

from mokuro import MokuroGenerator
from mokuro import __version__
from mokuro.legacy.overlay_generator import generate_legacy_html
from mokuro.utils import embed_mokuro_in_archive, bundle_to_cbz
from mokuro.volume import VolumeCollection


def run(
    *paths: Optional[Sequence[Union[str, Path]]],
    parent_dir: Optional[Union[str, Path]] = None,
    pretrained_model_name_or_path: str = "kha-white/manga-ocr-base",
    force_cpu: bool = False,
    disable_confirmation: bool = False,
    disable_ocr: bool = False,
    ignore_errors: bool = False,
    no_cache: bool = False,
    unzip: bool = False,
    legacy_html: bool = False,
    as_one_file: bool = True,
    ocr_batch_size: int = 16,
    single_file: bool = False,
    bundle: bool = False,
    keep_source: bool = False,
    install_shortcut: bool = False,
    uninstall_shortcut: bool = False,
    notify: bool = False,
):
    """
    Process manga volumes with mokuro.

    Args:
        paths: Paths to manga volumes. Volume can be a directory, a zip file or a cbz file.
        parent_dir: Parent directory to scan for volumes. If provided, all volumes inside this directory will be processed.
        pretrained_model_name_or_path: Name or path of the manga-ocr model.
        force_cpu: Force the use of CPU even if CUDA is available.
        disable_confirmation: Disable confirmation prompt. If False, the user will be prompted to confirm the list of volumes to be processed.
        disable_ocr: Disable OCR processing. Generate mokuro/HTML files without OCR results.
        ignore_errors: Continue processing volumes even if an error occurs.
        no_cache: Do not use cached OCR results from previous runs (_ocr directories).
        unzip: Extract volumes in zip/cbz format in their original location.
        legacy_html: Enable legacy HTML output (default: False). If True, acts as if --unzip is True.
        as_one_file: Applies only to legacy HTML. If False, generate separate CSS and JS files instead of embedding them in the HTML file.
        ocr_batch_size: Batch size for OCR inference.
        version: Print the version of mokuro and exit.
        single_file: Output a single self-contained .cbz archive with embedded .mokuro (removes loose metadata/cache).
        bundle: Bundle directory inputs into a single-file .cbz archive with embedded .mokuro and clean up loose scans/cache.
        keep_source: When bundling a directory, keep the original loose images folder alongside the .cbz.
        install_shortcut: Install right-click context menu / Quick Action shortcuts in Finder / Explorer.
        uninstall_shortcut: Remove right-click context menu / Quick Action shortcuts.
        notify: Show desktop notifications on start and completion.
    """

    if version:
        print(f"{__version__}")
        return

    # Handle Python Fire treating flags like -bundle / --bundle as consuming the next path argument
    if isinstance(bundle, (str, Path)):
        paths = (bundle,) + tuple(paths)
        bundle = True
    if isinstance(single_file, (str, Path)):
        paths = (single_file,) + tuple(paths)
        single_file = True
    if isinstance(notify, (str, Path)):
        paths = (notify,) + tuple(paths)
        notify = True
    if isinstance(install_shortcut, (str, Path)):
        paths = (install_shortcut,) + tuple(paths)
        install_shortcut = True
    if isinstance(uninstall_shortcut, (str, Path)):
        paths = (uninstall_shortcut,) + tuple(paths)
        uninstall_shortcut = True

    if install_shortcut:
        from mokuro.integration import install_shortcuts
        install_shortcuts()
        return

    if uninstall_shortcut:
        from mokuro.integration import uninstall_shortcuts
        uninstall_shortcuts()
        return

    if notify:
        from mokuro.integration import run_with_notifications
        run_with_notifications(
            *paths,
            parent_dir=parent_dir,
            pretrained_model_name_or_path=pretrained_model_name_or_path,
            force_cpu=force_cpu,
            disable_ocr=disable_ocr,
            no_cache=no_cache,
            unzip=unzip,
            legacy_html=legacy_html,
            as_one_file=as_one_file,
            ocr_batch_size=ocr_batch_size,
        )
        return

    if disable_ocr:
        logger.info("Running with OCR disabled")

    if legacy_html:
        logger.warning(
            "Legacy HTML output is deprecated and will not be further developed. "
            "It's recommended to use .mokuro format and web reader instead. "
            "Legacy HTML will be disabled by default in the future. To explicitly enable it, run with option --legacy-html."
        )
        # legacy HTML works only with unzipped output
        unzip = True

    logger.info("Scanning paths...")

    # Forgiving parser: extract single-dash flags and auto-join unquoted paths with spaces
    raw_paths = []
    for p in paths:
        if isinstance(p, (list, tuple)):
            for sub_p in p:
                if sub_p is not None:
                    raw_paths.append(str(sub_p))
        elif p is not None:
            raw_paths.append(str(p))

    filtered_paths = []
    for p in raw_paths:
        p_str = p.strip()
        if p_str in ("-bundle", "-b", "--bundle"):
            bundle = True
        elif p_str in ("-single_file", "-s", "--single_file", "--single-file"):
            single_file = True
        elif p_str in ("-keep_source", "-k", "--keep_source", "--keep-source"):
            keep_source = True
        elif p_str in ("-notify", "-n", "--notify"):
            notify = True
        elif p_str in ("-disable_confirmation", "-y", "-yes", "--yes", "--disable_confirmation", "--disable-confirmation"):
            disable_confirmation = True
        elif p_str in ("-disable_ocr", "--disable_ocr", "--disable-ocr"):
            disable_ocr = True
        elif p_str in ("-force_cpu", "--force_cpu", "--force-cpu"):
            force_cpu = True
        elif p_str in ("-ignore_errors", "--ignore_errors", "--ignore-errors"):
            ignore_errors = True
        elif p_str in ("-no_cache", "--no_cache", "--no-cache"):
            no_cache = True
        elif p_str in ("-unzip", "--unzip"):
            unzip = True
        elif p_str in ("-legacy_html", "--legacy_html", "--legacy-html"):
            legacy_html = True
        elif p_str.startswith("-") and not Path(p_str).exists():
            logger.warning(f"Unrecognized flag: {p_str}")
        else:
            filtered_paths.append(p)

    # Reconstruct unquoted space-split paths (e.g. ['manga/チェンソーマン', 'v24'])
    resolved_paths = []
    i = 0
    while i < len(filtered_paths):
        curr = str(filtered_paths[i])
        curr_path = Path(curr).expanduser().absolute()
        if curr_path.exists():
            resolved_paths.append(curr_path)
            i += 1
            continue

        joined = curr
        found_match = False
        for j in range(i + 1, len(filtered_paths)):
            joined += " " + str(filtered_paths[j])
            joined_path = Path(joined).expanduser().absolute()
            if joined_path.exists():
                resolved_paths.append(joined_path)
                i = j + 1
                found_match = True
                break

        if not found_match:
            resolved_paths.append(curr_path)
            i += 1

    paths_ = []
    for path_normalized in resolved_paths:
        try:
            path_valid = path_normalized.exists()
        except OSError:
            path_valid = False

        if path_valid:
            paths_.append(path_normalized)
        else:
            logger.error(f"Invalid path: {path_normalized}")
            return 0

    paths = paths_

    if parent_dir is not None:
        for p in Path(parent_dir).expanduser().absolute().iterdir():
            if (
                p not in paths
                and (p.is_dir() and p.stem != "_ocr")
                or (p.is_file() and p.suffix.lower() in {".zip", ".cbz"})
            ):
                paths.append(p)

    vc = VolumeCollection()

    for path_in in paths:
        vc.add_path_in(path_in)

    if len(vc) == 0:
        logger.error("Found no paths to process. Did you set the paths correctly?")
        return

    for title in vc.titles.values():
        title.set_uuid()

    status_counter = Counter()

    print(f"\nFound {len(vc)} volumes:\n")

    for volume in vc:
        print(volume)
        status_counter[volume.status] += 1

    msg = "\nEach of the paths above will be treated as one volume.\n"
    print(msg)

    if not disable_confirmation:
        inp = input("\nContinue? [yes/no]")
        if inp.lower() not in ("y", "yes"):
            return

    mg = MokuroGenerator(
        pretrained_model_name_or_path=pretrained_model_name_or_path,
        force_cpu=force_cpu,
        disable_ocr=disable_ocr,
        ocr_batch_size=ocr_batch_size,
    )

    with TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # unzip == True means that zipped volumes will be unzipped in their original location
        # in that case, we don't use a temporary directory
        if unzip:
            tmp_dir = None

        num_sucessful = 0
        for i, volume in enumerate(vc):
            logger.info(f"Processing {i + 1}/{len(vc)}: {volume.path_in}")

            try:
                volume.unzip(tmp_dir)
                mg.process_volume(volume, ignore_errors=ignore_errors, no_cache=no_cache)
                if legacy_html:
                    generate_legacy_html(volume, as_one_file=as_one_file, ignore_errors=ignore_errors)

                # Single-file / archive bundling
                archive_paths = [p for p in volume.paths_in if p.is_file() and p.suffix.lower() in {".cbz", ".zip"}]
                if archive_paths:
                    orig_archive = archive_paths[0]
                    embed_mokuro_in_archive(orig_archive, volume.path_mokuro)
                    logger.info(f"Embedded OCR metadata inside {orig_archive}")
                    if single_file or bundle:
                        _cleanup_volume_mess(volume, remove_source_dir=False)

                elif (single_file or bundle) and volume.path_in.is_dir():
                    cbz_path = bundle_to_cbz(volume.path_in, volume.path_mokuro)
                    logger.info(f"Bundled volume into single file: {cbz_path}")
                    if cbz_path.is_file() and cbz_path.stat().st_size > 0:
                        _cleanup_volume_mess(volume, remove_source_dir=not keep_source)

            except Exception:
                logger.exception(f"Error while processing {volume.path_in}")
            else:
                num_sucessful += 1

        logger.info(f"Processed successfully: {num_sucessful}/{len(vc)}")
        return num_sucessful


def _cleanup_volume_mess(volume: Volume, remove_source_dir: bool = False):
    """Remove loose .mokuro file, _ocr cache, and optionally source directory."""
    if volume.path_mokuro.is_file():
        try:
            volume.path_mokuro.unlink()
            logger.debug(f"Removed loose metadata: {volume.path_mokuro}")
        except OSError:
            pass

    if volume.path_ocr_cache.is_dir():
        shutil.rmtree(volume.path_ocr_cache, ignore_errors=True)
        logger.debug(f"Removed OCR cache: {volume.path_ocr_cache}")

    parent_ocr = volume.path_ocr_cache.parent
    if parent_ocr.is_dir():
        try:
            if not any(parent_ocr.iterdir()):
                parent_ocr.rmdir()
        except OSError:
            pass

    if remove_source_dir and volume.path_in.is_dir():
        shutil.rmtree(volume.path_in, ignore_errors=True)
        logger.info(f"Cleaned up source scans folder: {volume.path_in}")


if __name__ == "__main__":
    fire.Fire(run)
