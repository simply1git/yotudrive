# YotuDrive 2.0 - Final Production Version 🚀
### Infinite Cloud Storage on YouTube

**YotuDrive** is a revolutionary file storage system that transforms YouTube into unlimited cloud storage. It encodes any file into compression-resistant video frames with Reed-Solomon error correction, allowing perfect data recovery even after YouTube's compression.

---

## 🌐 Live Platform
- **Frontend**: https://yotudrive.vercel.app
- **Backend API**: https://yotudrive.onrender.com

## ✨ Key Features

*   **Robust Encoding Engine**: Custom **Block-Based Monochrome Encoding** (4x4 pixel blocks) designed to survive YouTube's aggressive compression
*   **Advanced Error Correction**: **Reed-Solomon (RS)** codes with configurable ECC bytes (default 10, range 1-50) ensure data integrity
*   **Military-Grade Security**: **Fernet (AES-128)** encryption with PBKDF2 key derivation and per-file salts
*   **Modern Web Interface**: Clean, responsive UI with real-time progress tracking, theme switching (light/dark), and advanced settings
*   **YouTube Integration**: Automated video downloads via `yt-dlp` with frame extraction
*   **Cross-Platform**: Works on any device with a web browser
*   **Hardware Acceleration**: Supports NVIDIA (NVENC), Intel (QSV), and AMD (AMF) codecs for faster encoding
*   **Large File Support**: Automatic splitting of files > specified size (MB) into chunks, each encoded separately
*   **Batch Processing**: Upload and encode multiple files in a single session
*   **Compression Options**: Configurable compression (currently Deflate/fast and Store/no compression; architecture-ready for LZMA/BZIP2)
*   **JWT Authentication**: Secure login with email/password and Google OAuth
*   **Real-time Analytics**: Track storage usage, file count, and upload history
*   **Theme Switching**: Light and dark mode with user preference persistence
*   **Advanced Upload Settings**: Customizable ECC bytes, hardware accel, compression, and split size

---

## 🔄 How It Works

### Upload Process
1. **File Selection**: User selects files and configures advanced settings (ECC bytes, hardware acceleration, compression, split size)
2. **Preprocessing**: Files are temporarily stored and optionally encrypted with AES-256
3. **Splitting (if needed)**: Large files are divided into chunks based on split size (MB)
4. **Encoding**: Each file/chunk is converted to binary, Reed-Solomon ECC is added, and data is mapped to 4x4 monochrome pixel blocks
5. **Frame Generation**: Data blocks are rendered as PNG frames (black/white pixels)
6. **Video Stitching**: Frames are combined into MP4 using FFmpeg with selected hardware acceleration
7. **Storage**: Videos are saved, metadata stored in JSON database
8. **Download**: User receives download links for all encoded video parts

### Recovery Process
1. **URL Input**: User provides YouTube video URL
2. **Download**: yt-dlp downloads the video and extracts frames
3. **Decoding**: Frames are processed, ECC corrects errors, binary data reconstructed
4. **Assembly**: If multiple parts, chunks are joined back to original file
5. **Decryption**: AES-256 decryption if password was used
6. **Download**: Recovered file available for download

### Advanced Features
- **Error Correction**: Reed-Solomon protects against YouTube compression artifacts
- **Hardware Acceleration**: GPU acceleration for faster video encoding (NVENC/QSV/AMF)
- **Large File Handling**: Splits oversized files for YouTube upload limits
- **Batch Encoding**: Multiple files processed in parallel
- **Theme UI**: Persistent light/dark mode switching
- **Settings Persistence**: Advanced options saved in localStorage

---

## 🚀 Quick Start (Online Platform)

### 1. Upload & Encode Files
1. Visit https://yotudrive.vercel.app
2. Login with email/password or Google account
3. Click "Upload Files" and select any file (max 100MB per chunk)
4. Configure advanced settings: ECC bytes, hardware accel, compression, split size
5. System automatically encodes to video frames
6. Download the encoded MP4 video(s)
7. Upload to YouTube (set as Unlisted or Public)

### 2. Recover Files
1. Copy YouTube video URL(s)
2. Paste in "Recover Files" section
3. System downloads and extracts frames
4. Decodes back to original file
5. Download recovered file

---

## 🏠 Local Development

### Installation
```bash
# Clone repository
git clone https://github.com/yourusername/yotudrive.git
cd yotudrive

# Install dependencies
pip install -r requirements.txt

# Run backend API (Flask)
python app.py

# Launch desktop GUI
python -m src.main_gui
```

### Environment Variables
```bash
SECRET_KEY=your_secret_key_here
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://yotudrive.vercel.app/auth/callback
```

---

## 🏗️ Technical Architecture

### Backend Endpoints
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/google` - Google OAuth login
- `POST /api/upload/start` - Initialize upload session
- `POST /api/upload/process` - File encoding with settings
- `POST /api/recover/start` - File recovery from YouTube (single video or playlist with auto-join)
- `GET /api/files` - List user files
- `GET /api/analytics` - User analytics and stats
- `POST /api/youtube/upload` - Optional YouTube Data API upload for encoded videos (OAuth-based)
- `GET /download/<filename>` - Secure file downloads

### Core Components
- **Engine (`src/engine.py`)**: High-level encode/decode/split/playlist orchestration shared by web and desktop UIs
- **Encoder (`src/encoder.py`)**: Converts files to video frames with Reed-Solomon ECC and streaming-friendly encryption
- **Decoder (`src/decoder.py`)**: Recovers files from video frames (including V5 streaming mode and header majority recovery)
- **YouTube Storage (`src/youtube.py`)**: Handles robust video downloads via yt-dlp
- **Google Integration (`src/google_integration.py`)**: OAuth + YouTube Data API upload support
- **Desktop GUI (`src/main_gui.py`)**: Local tabbed interface (My Files, Encode, Decode, Tools, Settings)
- **FFmpeg Utils (`src/ffmpeg_utils.py`)**: Video stitching with hardware acceleration
- **Database (`src/db.py`)**: JSON-based storage for metadata
- **Authentication**: JWT with Google OAuth support

### Technology Stack
- **Backend**: Flask (Python) with JWT authentication, CORS, Bcrypt
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript, Font Awesome
- **Database**: JSON-based file storage (Render-compatible)
- **Video Processing**: FFmpeg with hardware acceleration (NVENC/QSV/AMF)
- **YouTube Integration**: yt-dlp for automated downloads
- **Error Correction**: Reed-Solomon library for data integrity
- **Encryption**: Cryptography library for AES-256

### Data Flow
```
File Upload → Encryption → Splitting → Encoding → Frame Generation → Video Stitching → Download Links
                      ↓
YouTube Upload ← Video Storage
                      ↓
Video Download → Frame Extraction → Decoding → Joining → Decryption → File Recovery
```

---

## 🔒 Security Features
- JWT-based authentication with secure token handling and expiration
- Secure filename validation and sanitization using Werkzeug
- Input validation and XSS protection
- CORS protection for API endpoints
- Comprehensive error handling and logging
- Fernet (AES-128) encryption for sensitive data with per-file salts and PBKDF2 key derivation
- PBKDF2 key derivation for encryption keys
- Secure temporary file handling with automatic cleanup

---

## 🚀 Deployment
- **Backend**: Render (https://yotudrive.onrender.com) - Flask app with Gunicorn
- **Frontend**: Vercel (https://yotudrive.vercel.app) - Static HTML deployment
- **Database**: JSON file storage (compatible with Render's file system)
- **File Storage**: Temporary directories with automatic cleanup
- **Environment**: Production-ready with environment variables

---

## 📊 Performance
- Supports files up to 100MB per chunk
- Automatic cleanup of temporary files and frames
- Efficient parallel frame extraction and encoding
- Hardware-accelerated video processing (GPU support)
- Real-time progress tracking and status updates
- Optimized for mobile and desktop browsers
- Streaming file processing for memory efficiency

---

## 🔧 Troubleshooting

### Common Issues
1. **Upload Fails**: Check file size (max 100MB/chunk), network connection, and advanced settings
2. **Recovery Fails**: Ensure YouTube URL is valid, video is accessible, and not private/deleted
3. **Login Issues**: Clear browser cache/cookies, check Google OAuth setup
4. **Slow Processing**: Use hardware acceleration, reduce file size, check internet speed
5. **Theme Not Switching**: Clear localStorage or reset browser settings

### Error Codes
- `400`: Bad Request (invalid input, no files)
- `401`: Unauthorized (invalid/expired token)
- `404`: File/URL not found
- `500`: Server error (check backend logs)

### Debug Tips
- Check browser console for frontend errors
- View network tab for API request failures
- Use browser developer tools for theme/JS issues
- Test with small files first

---

## 📝 API Reference

### Authentication
```javascript
// Login
POST /api/auth/login
Body: { "email": "user@example.com", "password": "password" }

// Google OAuth
GET /auth/google
```

### Upload
```javascript
// Start upload
POST /api/upload/start
Headers: Authorization: Bearer <token>
Body: { "files": [{"name": "file.txt", "size": 1234}] }

// Process upload
POST /api/upload/process
Headers: Authorization: Bearer <token>
FormData: files, ecc_bytes, hw_accel, compression, split_size
```

### Recovery
```javascript
POST /api/recover/start
Headers: Authorization: Bearer <token>
Body: { "youtube_url": "https://youtube.com/watch?v=..." }
```

---

## 📈 Roadmap
- [ ] Mobile app development
- [ ] Multi-user collaboration features
- [ ] Advanced analytics dashboard
- [ ] Integration with other cloud storage
- [ ] API rate limiting and optimization
- [ ] Support for additional video codecs

---

## 📜 License
MIT License - see LICENSE file for details

## 🤝 Contributing
1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 💬 Support
For issues and support:
- GitHub Issues: https://github.com/yourusername/yotudrive/issues
- Email: support@yotudrive.com
- Live Chat: Available on web platform

---

**YotuDrive 2.0 - Store Anything, Anywhere, Forever** 🎥💾

*Infinite storage made simple through the power of YouTube.*
