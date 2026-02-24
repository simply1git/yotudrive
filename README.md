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
    The executable will be in `dist/YotuDrive/main_gui.exe`.

## ⚠️ Large File Support (>2GB)

YotuDrive automatically switches to **Streaming Mode (V5)** for large files.
*   **Memory Usage**: Remains low (~100MB) regardless of file size.
*   **Encryption**: Uses 1MB chunked encryption for security.
*   **Performance**: Optimized for multi-core CPUs.
