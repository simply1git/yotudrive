# YotuDrive 2.0 - Final Production Version 🚀
### Infinite Cloud Storage on YouTube

**YotuDrive** is a revolutionary file storage system that transforms YouTube into unlimited cloud storage. It encodes any file into compression-resistant video frames with Reed-Solomon error correction, allowing perfect data recovery even after YouTube's compression.

---

## 🌐 Live Platform
- **Frontend**: https://yotudrive.vercel.app
- **Backend API**: https://yotudrive.onrender.com

## ✨ Key Features

*   **Robust Encoding Engine**: Custom **Block-Based Monochrome Encoding** (4x4 pixel blocks) designed to survive YouTube's aggressive compression
*   **Advanced Error Correction**: **Reed-Solomon (RS)** codes with configurable ECC bytes ensure data integrity
*   **Military-Grade Security**: **AES-256 encryption** with PBKDF2 key derivation
*   **Modern Web Interface**: Clean, responsive UI with real-time progress tracking
*   **YouTube Integration**: Automated video downloads via `yt-dlp` with frame extraction
*   **Cross-Platform**: Works on any device with a web browser
*   **Hardware Acceleration**: Supports NVIDIA (NVENC), Intel (QSV), and AMD (AMF)
*   **Large File Support**: Handles files up to 100MB with streaming processing
*   **JWT Authentication**: Secure login with email/password and Google OAuth
*   **Real-time Analytics**: Track storage usage and file management

---

## 🚀 Quick Start (Online Platform)

### 1. Upload & Encode Files
1. Visit https://yotudrive.vercel.app
2. Login with email/password or Google account
3. Click "Upload Files" and select any file (max 100MB)
4. System automatically encodes to video frames
5. Download the encoded MP4 video
6. Upload to YouTube (set as Unlisted or Public)

### 2. Recover Files
1. Copy YouTube video URL
2. Paste in "Recover Files" section
3. System downloads and extracts frames
4. Decodes back to original file
5. Download recovered file

---

## � Local Development

### Installation
```bash
# Clone repository
git clone https://github.com/yourusername/yotudrive.git
cd yotudrive

# Install dependencies
pip install -r requirements.txt

# Run backend
python app.py
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
- `POST /api/upload/process` - File encoding
- `POST /api/recover/start` - File recovery
- `GET /api/files` - List user files
- `GET /api/analytics` - User analytics
- `GET /download/<filename>` - Secure file downloads

### Core Components
- **Encoder**: Converts files to video frames with error correction
- **Decoder**: Recovers files from video frames
- **YouTube Manager**: Handles video downloads and frame extraction
- **Database**: JSON-based storage for file metadata
- **Authentication**: JWT tokens with Google OAuth support

### Technology Stack
- **Backend**: Flask (Python) with JWT authentication
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
- **Database**: JSON-based file storage (Render-compatible)
- **Video Processing**: FFmpeg with hardware acceleration
- **YouTube Integration**: yt-dlp for automated downloads
- **Error Correction**: Reed-Solomon implementation

---

## � Security Features
- JWT-based authentication with secure token handling
- Secure filename validation and sanitization
- Input validation and XSS protection
- CORS protection for API endpoints
- Comprehensive error handling and logging
- AES-256 encryption for stored data

---

## 🚀 Deployment
- **Backend**: Render (https://yotudrive.onrender.com)
- **Frontend**: Vercel (https://yotudrive.vercel.app)
- **Database**: JSON file storage (Render-compatible)
- **File Storage**: Temporary files with automatic cleanup

---

## 📊 Performance
- Supports files up to 100MB
- Automatic cleanup of temporary files
- Efficient frame extraction and encoding
- Hardware-accelerated video processing
- Real-time progress tracking
- Optimized for mobile and desktop

---

## 🔧 Troubleshooting

### Common Issues
1. **Upload Fails**: Check file size (max 100MB) and format
2. **Recovery Fails**: Ensure YouTube URL is valid and video is accessible
3. **Login Issues**: Clear browser cache and cookies
4. **Slow Processing**: Check internet connection and try smaller files

### Error Codes
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (invalid token)
- `404`: File not found
- `500`: Server error (check logs)

---

## � License
MIT License - see LICENSE file for details

## 🤝 Contributing
1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## � Support
For issues and support:
- GitHub Issues: https://github.com/yourusername/yotudrive/issues
- Email: support@yotudrive.com
- Live Chat: Available on web platform

---

**YotuDrive 2.0 - Store Anything, Anywhere, Forever** 🎥💾

*Infinite storage made simple through the power of YouTube.*
