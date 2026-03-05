# YotuDrive Platform Documentation

## 1. Executive Summary
**YotuDrive** is a sophisticated software platform that transforms YouTube into an unlimited, free cloud storage drive. By encoding arbitrary binary files (documents, archives, executables) into compression-resistant video frames, YotuDrive allows users to upload data to YouTube and retrieve it later with bit-perfect integrity.

The platform is built with robustness as its core principle, utilizing advanced error correction, redundancy, and encryption to survive YouTube's aggressive video compression algorithms.

---

## 2. Core Features

### 2.1. Robust Encoding Engine
*   **Block-Based Monochrome Encoding**: Converts binary bits into 2x2 (or larger) pixel blocks.
    *   **0** = Black Block
    *   **1** = White Block
*   **Compression Resistance**: Designed to withstand chroma subsampling (4:2:0) and bitrate reduction.
*   **Hardware Acceleration**: Supports NVIDIA (NVENC), Intel (QSV), and AMD (AMF) for high-speed encoding.

### 2.2. Advanced Data Integrity
*   **Reed-Solomon Error Correction (ECC)**: Adds parity bytes to every data block, allowing the system to reconstruct corrupted data.
*   **Header Redundancy (V3/V5)**: Stores **5 copies** of the file metadata header at the start of the video. Uses "Majority Vote" logic to recover the header even if all copies are partially corrupted.
*   **Checksum Verification**: Every file includes an MD5 checksum in the header to verify integrity upon restoration.

### 2.3. Security & Privacy
*   **Encryption**: Uses **Fernet (AES-128)** symmetric encryption.
*   **Key Derivation**: Passwords are hashed using **PBKDF2HMAC** (SHA-256) with a unique salt per file.
*   **Chunked Encryption (V5)**: Large files are encrypted in 1MB chunks, allowing for secure streaming without loading the entire file into RAM.

### 2.4. Large File Handling
*   **Streaming Architecture**: Capable of processing files >100GB with minimal RAM usage (~100MB).
*   **Auto-Splitting**: Automatically splits files larger than 10GB (configurable) into parts (e.g., `.001`, `.002`) to bypass YouTube's 12-hour video limit.
*   **Playlist Restoration**: Can restore an entire sequence of split files from a single YouTube Playlist URL.
*   **Auto-Join**: Automatically detects split parts during restoration and merges them back into the original file.

### 2.5. Compression
*   **Algorithms**: Supports **Deflate** (Fast), **LZMA** (Best), **BZIP2**, and **Store** (No Compression).
*   **Smart Defaults**: Defaults to "Fast" (Deflate Level 1) to balance speed and size.

---

## 3. Technical Architecture

### 3.1. Data Flow
1.  **Input**: Binary File -> Compression (Optional) -> Encryption (Optional).
2.  **ECC**: Data is chunked into 223-byte blocks + 32 parity bytes = 255 bytes (Reed-Solomon).
3.  **Frame Generation**: Bits are mapped to a 1920x1080 grid.
    *   *Example*: Block Size 2 = 960x540 effective resolution = 518,400 bits per frame (~64KB).
4.  **Video Encoding**: Frames are stitched into an MP4 video using FFmpeg (lossless or high-bitrate settings).
5.  **Upload**: User uploads video to YouTube.
6.  **Download**: `yt-dlp` downloads the video.
7.  **Frame Extraction**: FFmpeg extracts frames to PNG.
8.  **Decoding**:
    *   **Block Averaging**: Calculates the average brightness of each 2x2 block.
    *   **Thresholding**: >128 = 1, <128 = 0.
    *   **ECC**: Reed-Solomon corrects any bit flips.
    *   **Reassembly**: Data is decrypted and decompressed.

### 3.2. Header Specification (Version 5)
The first 1024 bytes of the data stream contain the header:
*   **Magic**: `YOTU` (4 bytes)
*   **Version**: `0x05` (1 byte)
*   **Flags**: Compression/Encryption/Chunked (1 byte)
*   **Block Size**: e.g., 2 (1 byte)
*   **ECC Bytes**: e.g., 32 (1 byte)
*   **Payload Length**: 64-bit Integer (8 bytes)
*   **Checksum**: MD5 (16 bytes)
*   **Salt**: Random 16 bytes for encryption
*   **Original Size**: 64-bit Integer (8 bytes)
*   **Header Copies**: Number of repetitions (1 byte)
*   **Filename Length**: (1 byte)
*   **Filename**: UTF-8 String (Variable)
*   **CRC32**: Checksum of the header itself (4 bytes)

---

## 4. Installation & Setup

### 4.1. Prerequisites
*   **OS**: Windows 10/11 (Recommended), Linux, macOS.
*   **Python**: Version 3.10, 3.11, or 3.12. (Do **NOT** use 3.13+).
*   **FFmpeg**: Bundled automatically via `imageio-ffmpeg`, but system FFmpeg is supported.

### 4.2. Setup Steps
1.  **Clone Repository**:
    ```bash
    git clone <repo_url>
    cd yotudrive
    ```
2.  **Create Virtual Environment**:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

---

## 5. Usage Guide (GUI)

Launch the application via:
```bash
python src/main_gui.py
```

### 5.1. "My Files" Tab
*   **View**: Lists all files currently tracked in the local database (`yotudrive.json`).
*   **Actions**:
    *   **Delete**: Removes the file record (and local file if selected).
    *   **Verify**: Checks if the local file matches the database record.

### 5.2. "Encode (Upload)" Tab
1.  **Select File**: Choose a file or folder to upload.
2.  **Configure**:
    *   **Block Size**: Smaller = More Capacity, Larger = More Robust. (Default: 2).
    *   **Threads**: CPU threads for processing.
3.  **Encode**: Generates the video file.
4.  **Register**: After manually uploading to YouTube, paste the **Video ID** to link it to the file.

### 5.3. "Decode (Restore)" Tab
1.  **Source**:
    *   **Local Video**: Select a video file on your disk.
    *   **YouTube**: Paste a Video URL, Video ID, or **Playlist URL**.
2.  **Output**: Select where to save the restored file.
3.  **Password**: Enter if the file was encrypted.
4.  **Start**:
    *   Downloads video (if YouTube).
    *   Extracts frames.
    *   Decodes and verifies checksum.
    *   **Auto-Joins** if it detects split parts (e.g., `.001`).

### 5.4. "Tools" Tab
*   **Verify Video Integrity**: Checks if a video is a valid YotuDrive archive without fully restoring it.
*   **Auto-Join Tool**: Manually join split files (`.001`, `.002`, etc.).
*   **Theme**: Change UI appearance (Light/Dark).

---

## 6. Configuration & Tuning

### 6.1. `settings.json`
Located in the root directory, this file persists user preferences:
*   `block_size`: Pixel size of a data block (Default: 2).
*   `threads`: Number of parallel worker threads.
*   `theme`: UI Theme name.
*   `encoder`: `libx264` (Software) or `h264_nvenc` (NVIDIA), etc.

### 6.2. Performance Tuning
*   **Threads**: Set to `CPU Cores - 1` for best performance.
*   **Block Size**:
    *   **1**: Max Capacity (~120KB/frame). High risk of corruption on YouTube.
    *   **2**: Balanced (~60KB/frame). Recommended.
    *   **4**: High Robustness (~15KB/frame). Use for 4K uploads or bad connections.

---

## 7. Troubleshooting

### Common Issues
1.  **"FFmpeg not found"**:
    *   Ensure `imageio-ffmpeg` is installed (`pip install imageio-ffmpeg`).
    *   Or install FFmpeg system-wide and add to PATH.
2.  **"YouTube Download Failed"**:
    *   Update `yt-dlp`: `pip install --upgrade yt-dlp`.
    *   If age-gated, provide a `cookies.txt` file in the Restore tab.
3.  **"Checksum Invalid"**:
    *   The video quality on YouTube might be too low. Ensure you download the **highest quality** (1080p/4K).
    *   Try increasing **Block Size** (e.g., to 4) for future uploads.

---

## 8. Developer Notes

### 8.1. Project Structure
*   `src/`: Source code.
    *   `gui.py`: Main UI logic.
    *   `encoder.py` / `decoder.py`: Core logic.
    *   `ffmpeg_utils.py`: FFmpeg wrappers.
    *   `db.py`: JSON database handler.
*   `logs/`: Execution logs.
*   `tests/`: Unit tests.

### 8.2. Building the Executable
**Constraint**: Do **NOT** build the executable until the application is fully verified.

Command:
```bash
python build_exe.py
```
Output: `dist/YotuDrive/`
