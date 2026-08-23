# faster-mokuro

A performance-focused fork of [mokuro](https://github.com/kha-white/mokuro) with batched OCR inference, parallel image prefetching, and Apple Silicon (MPS) optimizations.

Read Japanese manga with selectable text inside a browser.

**See demo: https://kha-white.github.io/manga-demo**

https://user-images.githubusercontent.com/22717958/164993274-3e8d1650-9be3-457d-84cb-f92f9598cd5a.mp4

<sup>Demo contains excerpt from [Manga109-s dataset](http://www.manga109.org/en/download_s.html). うちの猫’ず日記 © がぁさん</sup>

mokuro is aimed towards Japanese learners who want to read manga in Japanese with a pop-up dictionary like [Yomitan](https://github.com/themoeway/yomitan).
It works like this:
1. Perform text detection and OCR for each page.
2. After processing a whole volume, generate a `.mokuro` file containing OCR results and metadata. All processing is done offline.
3. Load the `.mokuro` file together with manga images in [web reader](https://reader.mokuro.app/), which serves both as a reader and a catalog for processed series.

mokuro uses [comic-text-detector](https://github.com/dmMaze/comic-text-detector) for text detection and [manga-ocr](https://github.com/kha-white/manga-ocr) for OCR.

---

## What's new in faster-mokuro

This fork focuses on processing throughput and hardware utilization:

- **Batched OCR Inference**: The original implementation passed text crops to `manga-ocr` one by one (`batch_size=1`). We batch crops across each page (default: 16), which drastically cuts kernel dispatch overhead on CUDA and Apple Silicon (MPS).
- **Parallel Image Prefetching**: Disk I/O and image decoding run on background worker threads, overlapping CPU work with GPU inference.
- **Inference Mode & Bounded Decoding**: Text recognition runs inside `torch.inference_mode()` with bounded beam generation steps (`max_length=96`), speeding up autoregressive decoding without affecting output accuracy.
- **Apple Silicon Support**: Native MPS device selection and acceleration out of the box on macOS.

---

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/JanLancelot/faster-mokuro.git
cd faster-mokuro
git submodule update --init --recursive
pip install -e .
```

If you want GPU acceleration, ensure you have PyTorch installed for your platform:
- **CUDA (NVIDIA / Windows / Linux)**: See [PyTorch get-started](https://pytorch.org/get-started/locally/)
- **Apple Silicon (macOS)**: Supported natively via PyTorch MPS backend

---

## Usage

### Run on one volume

```bash
mokuro /path/to/manga/vol1
```

If your path contains spaces:

```bash
mokuro "/path/to/manga/volume 1"
```

### Run on multiple volumes

```bash
mokuro /path/to/manga/vol1 /path/to/manga/vol2 /path/to/manga/vol3
```

### Run on a directory containing multiple volumes

```bash
mokuro --parent_dir manga_title/
```

### One-Click OS Right-Click Integration (Finder / Explorer)

Process manga without touching the terminal:

1. **Install shortcut once:**
   ```bash
   mokuro --install_shortcut
   ```

2. **Process your manga:**
   - **macOS**: Right-click any manga folder, `.cbz`, or `.zip` file in Finder ➔ **Quick Actions** ➔ **Process with Mokuro**.
   - **Windows**: Right-click any manga folder, `.cbz`, or `.zip` file ➔ **Process with Mokuro**.
   - **Linux (Nautilus / Nemo)**: Right-click ➔ **Scripts** ➔ **Process with Mokuro**.

Mokuro will process the volume in the background and send a native desktop notification when it is finished.

To uninstall:
```bash
mokuro --uninstall_shortcut
```

---

### Options

```
--install_shortcut: Install right-click context menu / Quick Action shortcuts in Finder / Explorer.
--uninstall_shortcut: Remove right-click context menu / Quick Action shortcuts.
--notify: Run in background and show desktop notifications on start and completion.
--pretrained_model_name_or_path: Name or path of the manga-ocr model.
--force_cpu: Force the use of CPU even if CUDA/MPS is available.
--disable_confirmation: Disable confirmation prompt.
--disable_ocr: Disable OCR processing (generate layout only).
--ignore_errors: Continue processing volumes even if an error occurs.
--no_cache: Do not use cached OCR results from previous runs.
--unzip: Extract volumes in zip/cbz format in their original location.
--ocr_batch_size: Batch size for OCR inference on GPU/MPS (default: 16).
--legacy_html: Enable legacy HTML output (default: True).
--as_one_file: For legacy HTML, embed CSS/JS inside HTML.
--version: Print version and exit.
```

---

## See also

- [mokuro-reader](https://github.com/Gnathonic/mokuro-reader), a web reader for mokuro
- [Mokuro2Pdf](https://github.com/Kartoffel0/Mokuro2Pdf), CLI Ruby script to generate PDF files with selectable text
- [Xelieu's guide](https://lazyguidejp.github.io/jp-lazy-guide/setupMangaOnPC/), a comprehensive guide on reading and mining workflows

## Acknowledgments

- Original project by [kha-white/mokuro](https://github.com/kha-white/mokuro)
- [comic-text-detector](https://github.com/dmMaze/comic-text-detector)
- [Manga-Text-Segmentation](https://github.com/juvian/Manga-Text-Segmentation)
