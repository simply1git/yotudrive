import os
import json
import time
import uuid
import secrets
import jwt
import datetime
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from functools import wraps

# Import core YotuDrive modules
from src.db import FileDatabase
from src.enhanced_recovery import EnhancedRecoveryManager
from src.encoder import Encoder
from src.ffmpeg_utils import stitch_frames as stitch
from src.youtube import YouTubeStorage as YouTubeManager
from src.decoder import Decoder

from werkzeug.utils import secure_filename

import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEMP_FOLDER'] = 'temp'
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# Ensure directories exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['TEMP_FOLDER'], app.config['DOWNLOAD_FOLDER'], 'data']:
    os.makedirs(folder, exist_ok=True)

# Initialize Core Managers
db = FileDatabase()
recovery_manager = EnhancedRecoveryManager()

# Simple user storage for email login
USERS_FILE = 'data/users.json'
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump({}, f)

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

# Token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            if "Bearer " in token:
                token = token.split(" ")[1]
            # Standardize Secret Key and Algorithm for all login types
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
        except Exception as e:
            print(f"[ERROR] JWT Token validation failed: {str(e)}")
            return jsonify({'message': f'Invalid session. Please login again.'}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'version': '2.1.0'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    """Secure file download endpoint"""
    try:
        # Sanitize filename
        filename = secure_filename(filename)
        if not filename:
            return 'Invalid filename', 400
        
        # Check in uploads and downloads directories
        for directory in [app.config['UPLOAD_FOLDER'], app.config['DOWNLOAD_FOLDER']]:
            file_path = os.path.join(directory, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(directory, filename, as_attachment=True)
        
        return 'File not found', 404
        
    except Exception as e:
        logger.error(f"Download error for {filename}: {e}")
        return 'Download failed', 500

# --- Auth Endpoints ---

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '933593371934-i02bjdmk309b3a9b71qt4n3kop3edb60.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://yotudrive.vercel.app/auth/callback')

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name', email.split('@')[0] if email else 'User')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    users = load_users()
    if email in users:
        return jsonify({'error': 'User already exists'}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    user_id = str(uuid.uuid4())
    users[email] = {
        'id': user_id,
        'password_hash': hashed_password,
        'name': name
    }
    save_users(users)
    return jsonify({'message': 'User registered successfully'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    users = load_users()
    user_data = users.get(email)

    if not user_data or 'password_hash' not in user_data or not bcrypt.check_password_hash(user_data['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user_data['id'],
        'email': email,
        'auth_type': 'email',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'token': token,
        'user': {
            'id': user_data['id'],
            'email': email,
            'name': user_data['name'],
            'auth_type': 'email'
        }
    })

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    try:
        data = request.get_json()
        authorization_code = data.get('authorization_code')
        if not authorization_code:
            return jsonify({'error': 'Authorization code required'}), 400

        # Exchange authorization code for access token
        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': authorization_code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }

        token_response = requests.post(token_url, data=token_data)
        if token_response.status_code != 200:
            error_info = token_response.json()
            print(f"[ERROR] Token exchange failed: {error_info}")
            return jsonify({'error': f"Token exchange failed: {error_info.get('error_description', 'Unknown error')}"}), 400

        token_info = token_response.json()
        access_token = token_info.get('access_token')

        # Get user info from Google
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(user_info_url, headers=headers)

        if user_response.status_code != 200:
            return jsonify({'error': 'Failed to get user info'}), 400

        user_info = user_response.json()
        email = user_info.get('email')
        
        users = load_users()
        if email not in users:
            # Auto-register Google users
            user_id = str(uuid.uuid4())
            users[email] = {
                'id': user_id,
                'email': email,
                'name': user_info.get('name'),
                'google_id': user_info.get('id'),
                'picture': user_info.get('picture'),
                'auth_type': 'google',
                'created_at': time.time()
            }
            save_users(users)
        else:
            # Update existing user info from Google to ensure consistency
            users[email]['google_id'] = user_info.get('id')
            users[email]['picture'] = user_info.get('picture')
            users[email]['auth_type'] = 'google'
            users[email]['last_login'] = time.time()
            save_users(users)
        
        user_data = users[email]
        token = jwt.encode({
            'user_id': user_data['id'],
            'email': email,
            'auth_type': 'google',
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({
            'token': token,
            'user': {
                'id': user_data['id'],
                'email': email,
                'name': user_data['name'],
                'picture': user_info.get('picture'),
                'auth_type': 'google'
            }
        })
    except Exception as e:
        print(f"[EXCEPTION] Google auth error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# --- Core API Endpoints ---

@app.route('/api/upload/start', methods=['POST'])
@token_required
def start_upload(user_id):
    try:
        data = request.get_json()
        files = data.get('files', [])
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        upload_session_id = str(uuid.uuid4())
        return jsonify({
            'upload_session_id': upload_session_id,
            'status': 'ready'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/process', methods=['POST'])
@token_required
def process_upload(user_id):
    try:
        data = request.form
        upload_session_id = data.get('upload_session_id')
        files = request.files.getlist('files')
        
        # Get settings
        ecc_bytes = int(data.get('ecc_bytes', 10))
        hw_accel = data.get('hw_accel', 'auto')
        compression = data.get('compression', 'store')
        split_size = int(data.get('split_size', 0))
        
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files provided'}), 400
        
        results = []
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # Save uploaded file temporarily
                temp_file = os.path.join(app.config['TEMP_FOLDER'], secure_filename(file.filename))
                file.save(temp_file)
                file_size = os.path.getsize(temp_file)
                
                if split_size > 0 and file_size > split_size * 1024 * 1024:
                    # Split the file
                    with open(temp_file, 'rb') as f:
                        file_bytes = f.read()
                    chunk_size = split_size * 1024 * 1024
                    chunks = [file_bytes[i:i+chunk_size] for i in range(0, len(file_bytes), chunk_size)]
                    
                    for i, chunk in enumerate(chunks):
                        chunk_filename = f"{secure_filename(file.filename).rsplit('.', 1)[0]}_part{i+1}.{file.filename.split('.')[-1] if '.' in file.filename else ''}"
                        temp_chunk = os.path.join(app.config['TEMP_FOLDER'], chunk_filename)
                        with open(temp_chunk, 'wb') as f:
                            f.write(chunk)
                        
                        # Encode chunk
                        frames_dir = os.path.join(app.config['TEMP_FOLDER'], str(uuid.uuid4()))
                        os.makedirs(frames_dir, exist_ok=True)
                        
                        encoder = Encoder(temp_chunk, frames_dir, ecc_bytes=ecc_bytes, compression=compression)
                        encoder.encode()
                        
                        video_filename = chunk_filename.rsplit('.', 1)[0] + '.mp4'
                        video_file = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
                        
                        stitch(frames_dir, video_file, hw_accel=hw_accel)
                        
                        # Add to database
                        db.add_file(
                            file_name=chunk_filename,
                            video_id='',
                            file_size=os.path.getsize(video_file),
                            metadata={
                                'owner_id': user_id,
                                'upload_session': upload_session_id,
                                'video_path': video_file,
                                'original_filename': chunk_filename,
                                'processed_at': time.time(),
                                'part': i+1,
                                'total_parts': len(chunks)
                            }
                        )
                        
                        results.append({
                            'filename': chunk_filename,
                            'video_download_url': f'/download/{video_filename}'
                        })
                        
                        # Clean up
                        os.remove(temp_chunk)
                        shutil.rmtree(frames_dir)
                    
                    # Remove original temp_file
                    os.remove(temp_file)
                    
                else:
                    # Normal encoding
                    frames_dir = os.path.join(app.config['TEMP_FOLDER'], str(uuid.uuid4()))
                    os.makedirs(frames_dir, exist_ok=True)
                    
                    encoder = Encoder(temp_file, frames_dir, ecc_bytes=ecc_bytes, compression=compression)
                    encoder.encode()
                    
                    video_filename = secure_filename(file.filename).rsplit('.', 1)[0] + '.mp4'
                    video_file = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
                    
                    stitch(frames_dir, video_file, hw_accel=hw_accel)
                    
                    # Add to database
                    db.add_file(
                        file_name=secure_filename(file.filename),
                        video_id='',
                        file_size=os.path.getsize(video_file),
                        metadata={
                            'owner_id': user_id,
                            'upload_session': upload_session_id,
                            'video_path': video_file,
                            'original_filename': file.filename,
                            'processed_at': time.time()
                        }
                    )
                    
                    results.append({
                        'filename': file.filename,
                        'video_download_url': f'/download/{video_filename}'
                    })
                    
                    # Clean up
                    os.remove(temp_file)
                    shutil.rmtree(frames_dir)
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}")
                results.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'completed',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Upload processing error: {e}")
        return jsonify({'error': 'Upload processing failed'}), 500

@app.route('/api/recover/start', methods=['POST'])
@token_required
def start_recovery(user_id):
    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url')
        
        if not youtube_url:
            return jsonify({'error': 'YouTube URL required'}), 400
            
        # Validate YouTube URL
        if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Download and extract frames
        frames_dir = os.path.join(app.config['TEMP_FOLDER'], str(uuid.uuid4()))
        os.makedirs(frames_dir, exist_ok=True)
        
        try:
            youtube_manager = YouTubeManager()
            if youtube_manager.download(youtube_url, frames_dir):
                # Decode frames back to file
                output_filename = f'recovered_{uuid.uuid4().hex}.zip'
                output_file = os.path.join(app.config['DOWNLOAD_FOLDER'], output_filename)
                
                decoder = Decoder(frames_dir, output_file)
                decoder.run()
                
                # Clean up frames
                shutil.rmtree(frames_dir)
                
                return jsonify({
                    'recovery_id': str(uuid.uuid4()),
                    'status': 'completed',
                    'file_download_url': f'/download/{output_filename}'
                })
            else:
                return jsonify({'error': 'Failed to download YouTube video'}), 500
                
        except Exception as e:
            logger.error(f"Recovery processing error: {e}")
            # Clean up on error
            if os.path.exists(frames_dir):
                shutil.rmtree(frames_dir)
            return jsonify({'error': 'Recovery processing failed'}), 500
            
    except Exception as e:
        logger.error(f"Recovery error: {e}")
        return jsonify({'error': 'Recovery failed'}), 500

@app.route('/api/analytics', methods=['GET'])
@token_required
def get_analytics(user_id):
    try:
        all_files = db.list_files()
        user_files = [f for f in all_files if f.get('metadata', {}).get('owner_id') == user_id]
        total_size = sum(f.get('file_size', 0) for f in user_files)
        
        return jsonify({
            'total_files': len(user_files),
            'total_size': total_size,
            'files': user_files
        })
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        return jsonify({'error': 'Failed to get analytics'}), 500

@app.route('/api/files', methods=['GET'])
@token_required
def get_files(user_id):
    try:
        files = db.list_files()
        user_files = [f for f in files if f.get('metadata', {}).get('owner_id') == user_id]
        return jsonify({'files': user_files})
    except Exception as e:
        logger.error(f"Files list error: {e}")
        return jsonify({'error': 'Failed to get files'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
