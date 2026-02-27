import os
import json
import time
import uuid
import secrets
import jwt
import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from functools import wraps

# Import core YotuDrive modules
from src.db import FileDatabase
from src.enhanced_recovery import EnhancedRecoveryManager

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_urlsafe(32))
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Initialize Core Managers
db = FileDatabase()
recovery_manager = EnhancedRecoveryManager()

# Simple user storage for email login (In production, use a database)
USERS_FILE = 'data/users.json'
os.makedirs('data', exist_ok=True)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump({}, f)

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

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
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
        except Exception as e:
            return jsonify({'message': 'Token is invalid!'}), 401
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'version': '2.1.0'})

# --- Auth Endpoints ---

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

    if not user_data or not bcrypt.check_password_hash(user_data['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user_data['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        'token': token,
        'user': {
            'id': user_data['id'],
            'email': email,
            'name': user_data['name']
        }
    })

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
        data = request.get_json()
        upload_session_id = data.get('upload_session_id')
        files = data.get('files', [])
        
        results = []
        for file_info in files:
            video_id = f"yotu_{uuid.uuid4().hex[:12]}"
            db_id = db.add_file(
                file_name=file_info['name'],
                video_id=video_id,
                file_size=file_info.get('size', 0),
                metadata={
                    'owner_id': user_id,
                    'upload_session': upload_session_id,
                    'processed_at': time.time()
                }
            )
            results.append({
                'filename': file_info['name'],
                'status': 'completed',
                'video_id': video_id
            })
            
        return jsonify({
            'status': 'completed',
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/start', methods=['POST'])
@token_required
def start_recovery(user_id):
    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url')
        if not youtube_url:
            return jsonify({'error': 'YouTube URL required'}), 400
            
        recovery_id = recovery_manager.create_recovery_session(user_id, youtube_url)
        # Mock identification for quick UI feedback
        return jsonify({
            'recovery_id': recovery_id,
            'status': 'identified',
            'video_info': {'title': 'YouTube Video', 'channel': 'Unknown'}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
@token_required
def get_analytics(user_id):
    try:
        all_files = db.list_files()
        user_files = [f for f in all_files if f.get('owner_id') == user_id]
        total_size = sum(f.get('file_size', 0) for f in user_files)
        return jsonify({
            'total_files': len(user_files),
            'storage_used': f"{round(total_size / (1024*1024), 2)} MB",
            'storage_limit': '10 GB',
            'recoveries_this_month': 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
@token_required
def get_files(user_id):
    try:
        files = db.list_files()
        user_files = [f for f in files if f.get('owner_id') == user_id]
        return jsonify({'files': user_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
