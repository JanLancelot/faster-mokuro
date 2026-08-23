# faster-mokuro

A fast, streamlined fork of [mokuro](https://github.com/kha-white/mokuro) with batched OCR inference, Apple Silicon (MPS) acceleration, and one-click single-file CBZ packaging.

Read Japanese manga with selectable text in your browser and look up words with pop-up dictionaries like [Yomitan](https://github.com/themoeway/yomitan).

**Demo:** https://kha-white.github.io/manga-demo

https://user-images.githubusercontent.com/22717958/164993274-3e8d1650-9be3-457d-84cb-f92f9598cd5a.mp4

<sup>Demo excerpt from [Manga109-s dataset](http://www.manga109.org/en/download_s.html). うちの猫’ず日記 © がぁさん</sup>

---

## What's new in faster-mokuro

- **Batched OCR Inference**: Batches crop recognition per page (`batch_size=16` by default), drastically reducing kernel dispatch overhead on Apple Silicon (MPS) and CUDA.
- **Parallel Image Prefetching**: Background image decoding overlaps CPU disk I/O with GPU inference.
- **Single-File CBZ Output**: Embeds `.mokuro` metadata directly into `.cbz` archives (`--bundle`, `--single_file`) so you get one clean file without loose metadata or scratch `_ocr/` folders.
- **OS Right-Click Integration**: Process manga directly from macOS Finder (Quick Actions), Windows Explorer, or Linux file managers with native desktop notifications.
- **Bounded Decoding**: Runs inside `torch.inference_mode()` with bounded beam generation steps (`max_length=96`), speeding up autoregressive decoding without affecting output accuracy.

---

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/JanLancelot/faster-mokuro.git
cd faster-mokuro
git submodule update --init --recursive
pip install -e .
```

### Hardware Acceleration
- **Apple Silicon (macOS)**: Supported natively out of the box via PyTorch MPS backend.
- **CUDA (NVIDIA / Windows / Linux)**: Install PyTorch with CUDA support from [pytorch.org](https://pytorch.org/get-started/locally/).

---

## Usage

### Single-File CBZ Bundling

Create self-contained `.cbz` files with embedded OCR data that open directly in web readers without loose files:

```bash
# Bundle an image folder into a single .cbz with OCR embedded
mokuro --bundle "manga/Chainsaw Man vol 01"

# Process an existing .cbz file in-place and clean up loose cache
mokuro --single_file "manga/vol1.cbz"
```

### Standard Processing

```bash
# Process one volume
mokuro path/to/manga/vol1

# Process multiple volumes
mokuro path/to/vol1 path/to/vol2 path/to/vol3

# Scan and process all volumes inside a parent directory
mokuro --parent_dir manga_title/
```

### One-Click Right-Click Processing (Finder / Explorer)

Process manga directly from your file manager without opening a terminal:

1. **Install shortcut once:**
   ```bash
   mokuro --install_shortcut
   ```
2. **Right-click your manga:**
   - **macOS**: Right-click any folder or `.cbz` in Finder ➔ **Quick Actions** ➔ **Process with Mokuro**.
   - **Windows**: Right-click any folder or `.cbz` ➔ **Process with Mokuro**.
   - **Linux (Nautilus / Nemo)**: Right-click ➔ **Scripts** ➔ **Process with Mokuro**.

Mokuro will process the volume in the background and send a native desktop notification when finished.

To uninstall:
```bash
mokuro --uninstall_shortcut
```

---

## Options

```
--bundle: Bundle directory inputs into a single-file .cbz archive with embedded .mokuro and clean up cache.
--single_file: Output a single self-contained .cbz archive with embedded .mokuro (removes loose metadata/cache).
--keep_source: When bundling a directory, keep the original image folder alongside the .cbz (default: True).
--install_shortcut: Install right-click context menu / Quick Action shortcuts in Finder / Explorer.
--uninstall_shortcut: Remove right-click context menu / Quick Action shortcuts.
--notify: Run in background and show desktop notifications on start and completion.
--ocr_batch_size: Batch size for OCR inference on GPU/MPS (default: 16).
--pretrained_model_name_or_path: Name or path of the manga-ocr model.
--force_cpu: Force CPU execution even if CUDA/MPS is available.
--disable_confirmation: Disable confirmation prompt.
--disable_ocr: Disable OCR processing (generate layout only).
--ignore_errors: Continue processing volumes even if an error occurs.
--no_cache: Do not use cached OCR results from previous runs.
--unzip: Extract volumes in zip/cbz format in their original location.
--legacy_html: Enable legacy HTML output (default: False).
--as_one_file: For legacy HTML, embed CSS/JS inside HTML.
--version: Print version and exit.
```

---

## Readers & Tools

- [reader.mokuro.app](https://reader.mokuro.app/) / [mokuro-reader](https://github.com/Gnathonic/mokuro-reader) — Web readers with selectable text and pop-up dictionary support
- [Mokuro2Pdf](https://github.com/Kartoffel0/Mokuro2Pdf) — Convert mokuro output to PDF with selectable text
- [Yomitan](https://github.com/themoeway/yomitan) — Pop-up dictionary browser extension for Japanese text lookups
- [Xelieu's Guide](https://lazyguidejp.github.io/jp-lazy-guide/setupMangaOnPC/) — Comprehensive guide on Japanese manga reading and Anki mining setups

## Acknowledgments

- Original project by [kha-white/mokuro](https://github.com/kha-white/mokuro)
- [manga-ocr](https://github.com/kha-white/manga-ocr) by kha-white
- [comic-text-detector](https://github.com/dmMaze/comic-text-detector) by dmMaze
- [Manga-Text-Segmentation](https://github.com/juvian/Manga-Text-Segmentation) by juvian
