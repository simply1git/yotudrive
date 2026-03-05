# YotuDrive 🚀
### Infinite Cloud Storage on YouTube

**YotuDrive** is a professional-grade tool that transforms YouTube into an unlimited cloud storage drive. It encodes any file into a sequence of compression-resistant video frames, allowing you to upload them to YouTube and retrieve them later with perfect data integrity.

---

## 🌟 Key Features

*   **Robust Encoding Engine**: Uses a custom **Block-Based Monochrome Encoding** (4x4 pixel blocks) specifically designed to survive YouTube's aggressive compression algorithms (chroma subsampling, bitrate reduction).
*   **V3/V5 Header Redundancy**: Protects critical metadata by storing **5 copies** of the header frame.
    *   **V5 Streaming Protocol**: Supports files >70GB using chunked encryption and streaming processing to minimize RAM usage.
*   **Advanced Error Correction**: Implements **Reed-Solomon (RS)** codes with configurable ECC bytes.
*   **Security**: Uses **Fernet (AES-128)** encryption with PBKDF2 key derivation. V5 uses 1MB chunked encryption for secure streaming.
*   **Frame-Based Architecture**: Generates independent PNG frames, making the tool cross-platform and resilient to video container issues.
*   **File Management**: Built-in JSON database to track your uploaded files and their corresponding YouTube Video IDs.
*   **YouTube Integration**:
    *   **Download**: Automated video downloading and frame extraction via `yt-dlp`.
    *   **Upload**: Guided manual upload workflow with helper buttons to open YouTube Studio and copy file paths.
*   **Hardware Acceleration**:
    *   Supports **NVIDIA (NVENC)**, **Intel (QSV)**, and **AMD (AMF)** for faster video encoding.
    *   Automatic fallback to software (libx264) if hardware encoding fails.
*   **Customizable UI**:
    *   Switch between multiple **Light** and **Dark** themes (e.g., Cosmo, Darkly, Cyborg) via the Tools tab.
*   **Compression Options**:
    *   Choose between **Store** (No Compression), **Fast** (Deflate), **Best** (LZMA), or **BZIP2** to balance speed vs. file size.
*   **Large File Handling**:
    *   **Auto-Splitting**: Split large files (e.g., >10GB) into smaller chunks (100MB, 1GB, etc.) to bypass YouTube's 12-hour video limit.
    *   **Batch Processing**: Automatically encodes each chunk into a separate video.
    *   **Join Tool**: Built-in tool to easily combine restored chunks back into the original file.
    *   **Playlist Support**: Restore multiple files or split parts sequentially by providing a YouTube Playlist URL.
    *   **Auto-Join on Restore**: Automatically detects and joins split file parts (e.g., `.001`, `.002`) after downloading and decoding.
*   **Robustness**:
    *   **Persistent Logging**: Automatically saves detailed execution logs to `logs/` for troubleshooting.
    *   **Header Redundancy**: V5 Header stores checksums and metadata with 5x redundancy.
    *   **Streaming Restore**: Decodes large files (>70GB) by streaming data to disk, minimizing RAM usage.
    *   **Video Verification**: "Verify Integrity" tool checks if a video file is a valid YotuDrive archive and displays metadata.

## 🔧 Troubleshooting

### PowerShell "running scripts is disabled" Error
If you see an error like `cannot be loaded because running scripts is disabled on this system`, it means PowerShell's execution policy is restricting the activation script.

**Fix:**
Run the following command in PowerShell to allow local scripts:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then try activating the virtual environment again:
```powershell
.venv\Scripts\Activate.ps1
```

### Dependency Installation Issues
If `pip install` fails or hangs, try upgrading pip first:
```bash
python -m pip install --upgrade pip
```
Then install dependencies again:
```bash
python -m pip install -r requirements.txt
```


2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *(Requires `numpy`, `Pillow`, `tqdm`, `yt-dlp`)*
    
    > **⚠️ CRITICAL WARNING:** You must use **Python 3.10, 3.11, or 3.12**.
    > **DO NOT USE Python 3.14 or 3.13**. These versions are too new and will cause installation to hang or fail because they lack pre-built binaries for `numpy` and `Pillow`.

3.  **Install FFmpeg (Optional)**:
    *   YotuDrive now includes a bundled FFmpeg via `imageio-ffmpeg`, so manual installation is usually not required.
    *   However, if you prefer to use your system FFmpeg, you can still install it:
        *   **Windows**: [Download FFmpeg](https://ffmpeg.org/download.html)
        *   **Linux**: `sudo apt install ffmpeg`
        *   **macOS**: `brew install ffmpeg`

---

## 🚀 Usage Guide

## 🌐 Web App (Flask)

Run the new web console:

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

The web API is backed by the shared core engine (`src/core/engine.py`) and supports file listing, encode/decode job start + polling, video verify, settings management, manual upload registration, and optional OAuth upload job start.

For full desktop-equivalent pipeline orchestration (encode + stitch + optional roundtrip verify), use:

`POST /api/pipeline/encode-video/start`

For full decode orchestration from a local video source (extract + decode), use:

`POST /api/pipeline/decode-video/start`

API details are documented in `docs/api.md`.

## ✅ Continuous Integration

GitHub Actions workflow: `.github/workflows/ci.yml`

It runs:

- unit + smoke tests
- full-cycle integration test (`tests/test_full_cycle.py`)

## 🚢 Automated Releases

GitHub Actions release workflow: `.github/workflows/release.yml`

Trigger a release by pushing a semantic tag such as `v1.0.0`.

The workflow will:

- run core test gates (unit/smoke/full-cycle)
- build `dist/YotuDrive/YotuDrive.exe`
- package `dist/YotuDrive/` as `YotuDrive-<tag>-windows-x64.zip`
- generate `SHA256SUMS.txt`
- upload assets to the GitHub Release for that tag

## 🚀 Quick Start (GUI Mode)

For a user-friendly experience, simply run:
```bash
python src/main_gui.py
```
This launches the graphical interface where you can manage your files easily without using the command line.

## 💻 CLI Usage (Advanced)

If you prefer the command line:

### 1. Encode a File (Prepare for Upload)
Convert any file (zip, exe, txt, etc.) into a folder of video frames.

```bash
python -m src.cli encode <path_to_input_file> --output <output_frames_dir>
```
**Example**:
```bash
python -m src.cli encode my_data.zip --output data/frames
```
*   **Output**: Creates `frame_XXXX.png` images in `data/frames`.
*   **Database**: Automatically tracks the file locally.

### 2. Upload to YouTube
Since YouTube API has strict quotas, we use a reliable manual upload method.

**Step 1: Create Video from Frames**
Use the built-in `stitch` command to create a video file from your frames. This uses the bundled FFmpeg.

```bash
python -m src.cli stitch <frames_dir> <output_video_file>
```
**Example**:
```bash
python -m src.cli stitch data/frames output.mp4
```

**Step 2: Upload to YouTube**
*   Upload `output.mp4` to your YouTube channel (set as **Unlisted** or **Public**).
*   Copy the **Video ID** (e.g., `dQw4w9WgXcQ`).

### 3. Register the Upload
Link your file to the YouTube Video ID in the local database.

```bash
python -m src.cli register <filename> <video_id>
```
**Example**:
```bash
python -m src.cli register my_data.zip dQw4w9WgXcQ
```

### 4. List Stored Files
View all files you have tracked in YotuDrive.

```bash
python -m src.cli list
```

### 5. Download & Restore
Retrieve a file from YouTube using its Video ID.

```bash
python -m src.cli download <video_id> <output_frames_dir>
```
**Example**:
```bash
python -m src.cli download dQw4w9WgXcQ data/restored_frames
```
*   **Downloads** the video using `yt-dlp`.
*   **Extracts** frames to `data/restored_frames` using FFmpeg.

Then, decode the frames back to the original file:

```bash
python -m src.cli decode <output_frames_dir> <output_file_path>
```
**Example**:
```bash
python -m src.cli decode data/restored_frames data/restored_data.zip
```

---

## 🔧 Technical Architecture

*   **Encoder (`src/encoder.py`)**: Reads binary data, applies Error Correction (ECC), and maps bits to 4x4 pixel blocks.
    *   `0` -> Black Block
    *   `1` -> White Block
*   **Decoder (`src/decoder.py`)**: Reads video frames, samples the center pixel of each block (to avoid edge artifacts), and applies Majority Vote to recover the original bits.
*   **Database (`src/db.py`)**: Simple JSON-based storage (`yotudrive.json`) for metadata persistence.

## 🧱 V5 Core Foundation

The codebase now includes a modular foundation for production-style V5 development:

*   `src/header_v5.py`: Dedicated V5 header format, CRC validation, and majority-vote recovery.
*   `src/settings.py`: Centralized settings schema and JSON persistence for shared config.
*   `src/core/engine.py`: Unified core API for encode/decode/verify/list used by UI layers.
*   `src/youtube_api.py`: Optional OAuth upload integration layer for YouTube Data API v3.

See `docs/architecture_v5.md` for design details and rollout notes.

## 📦 Building from Source

To create a standalone executable for Windows (or your OS):

1.  **Install PyInstaller**:
    ```bash
    pip install pyinstaller
    ```

2.  **Run the Build Script**:
    ```bash
    python build_exe.py
    ```

3.  **Locate the Output**:
     The executable will be in `dist/YotuDrive/YotuDrive.exe`.

## 🛡️ Production Readiness

Use this checklist before every public release:

1. Validate in a clean environment (`python -m venv .venv_cleancheck` + `pip install -r requirements.txt`).
2. Run test gates:
    - `python -m unittest tests.test_core_engine tests.test_web_api_smoke tests.test_header_v5_module tests.test_settings_module tests.test_decoder_detection tests.test_encoder_executor_selection`
    - `python tests/test_full_cycle.py`
3. Build and smoke-test executable:
    - `python build_exe.py`
    - Launch `dist/YotuDrive/YotuDrive.exe` and run one encode/decode roundtrip.
4. Verify restored payload integrity with external hash tools (e.g., SHA-256).
5. Confirm logs are generated in `dist/YotuDrive/logs/` with no unhandled exceptions.

Windows frozen executable note:

- YotuDrive automatically uses `ThreadPoolExecutor` in frozen Windows builds for encoding stability.
- This avoids `BrokenProcessPool` failures observed with `ProcessPoolExecutor` in PyInstaller runtime.

For full release operations and go/no-go criteria, see `docs/release_runbook.md`.

## ⚠️ Large File Support (>2GB)

YotuDrive automatically switches to **Streaming Mode (V5)** for large files.
*   **Memory Usage**: Remains low (~100MB) regardless of file size.
*   **Encryption**: Uses 1MB chunked encryption for security.
*   **Performance**: Optimized for multi-core CPUs.
