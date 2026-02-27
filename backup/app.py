"""
YotuDrive 2.0 - Minimal OAuth Backend for Render
Handles Google OAuth authentication and basic API endpoints
"""

import os
import json
import time
import uuid
import secrets
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

# Import core YotuDrive modules
from src.db import FileDatabase
from src.enhanced_recovery import EnhancedRecoveryManager
from src.google_integration import YouTubeManager, GoogleDriveManager

from flask_cors import CORS

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config['SECRET_KEY'] = secrets.token_urlsafe(32)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Initialize Core Managers
db = FileDatabase()
recovery_manager = EnhancedRecoveryManager()

# Manual CORS headers
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

# Active sessions storage (in production, use Redis/database)
active_sessions = {}
upload_sessions = {}

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '933593371934-i02bjdmk309b3a9b71qt4n3kop3edb60.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://yotudrive.vercel.app/auth/callback')

@app.route('/')
def index():
    """Main dashboard - serve the frontend"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0.1',
        'services': {
            'api': 'active',
            'oauth': 'ready'
        }
    })

@app.route('/api/auth/google', methods=['POST', 'OPTIONS'])
def google_auth():
    """Handle Google OAuth callback with enhanced logging"""
    if request.method == 'OPTIONS':
        return _handle_preflight()

    try:
        data = request.get_json()
        print(f"[DEBUG] Received OAuth request data: {data}")
        
        if not data:
            print("[ERROR] No data provided in request")
            return jsonify({'error': 'No data provided'}), 400

        authorization_code = data.get('authorization_code')
        if not authorization_code:
            print("[ERROR] Authorization code missing")
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

        print(f"[DEBUG] Exchanging code for token with redirect_uri: {GOOGLE_REDIRECT_URI}")
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
            print(f"[ERROR] User info fetch failed: {user_response.status_code}")
            return jsonify({'error': 'Failed to get user info'}), 400

        user_info = user_response.json()
        print(f"[DEBUG] User authenticated: {user_info.get('email')}")

        session_id = str(uuid.uuid4())
        user_data = {
            'id': user_info.get('id'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture')
        }

        active_sessions[session_id] = {
            'user_data': user_data,
            'access_token': access_token,
            'created_at': time.time(),
            'expires_at': time.time() + 3600
        }

        return jsonify({
            'session_id': session_id,
            'user': user_data,
            'message': 'Login successful'
        })

    except Exception as e:
        print(f"[EXCEPTION] OAuth error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal Server Error: {str(e)}'}), 500

def _handle_preflight():
    response = jsonify({'status': 'ok'})
    origin = request.headers.get('Origin')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = '*'
        
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'authenticated': False}), 401

    session = active_sessions[session_id]

    # Check if session is expired
    if time.time() > session['expires_at']:
        del active_sessions[session_id]
        return jsonify({'authenticated': False}), 401

    return jsonify({
        'authenticated': True,
        'user': session['user_data'],
        'expires_in': int(session['expires_at'] - time.time())
    })

@app.route('/api/upload/start', methods=['POST'])
def start_upload():
    """Start file upload session"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        files = data.get('files', [])

        if not files:
            return jsonify({'error': 'No files provided'}), 400

        # Create upload session
        upload_session_id = str(uuid.uuid4())
        upload_sessions[upload_session_id] = {
            'session_id': session_id,
            'files': files,
            'created_at': time.time(),
            'status': 'started'
        }

        return jsonify({
            'upload_session_id': upload_session_id,
            'files': files,
            'status': 'ready'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/process', methods=['POST'])
def process_upload():
    """Process file upload with database registration"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        upload_session_id = data.get('upload_session_id')

        if not upload_session_id or upload_session_id not in upload_sessions:
            return jsonify({'error': 'Invalid upload session'}), 400

        # In production, we would use the actual uploaded files from a temp storage
        # and process them using the Encoder class.
        # For now, we simulate the logic and register in the database.
        
        results = []
        for file_info in upload_sessions[upload_session_id]['files']:
            # Create a unique video ID (simulating YouTube upload or local storage)
            video_id = f"yotu_{uuid.uuid4().hex[:12]}"
            
            # Register in FileDatabase
            db_id = db.add_file(
                file_name=file_info['name'],
                video_id=video_id,
                file_size=file_info.get('size', 0),
                metadata={
                    'mime_type': file_info.get('type'),
                    'owner_session': session_id,
                    'upload_session': upload_session_id,
                    'processed_at': time.time()
                }
            )
            
            results.append({
                'filename': file_info['name'],
                'status': 'completed',
                'db_id': db_id,
                'video_id': video_id,
                'size': file_info.get('size', 0)
            })

        # Update session status
        upload_sessions[upload_session_id]['status'] = 'completed'

        return jsonify({
            'results': results,
            'status': 'completed'
        })

    except Exception as e:
        print(f"[EXCEPTION] Upload process error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/start', methods=['POST'])
def start_recovery():
    """Start YouTube recovery using EnhancedRecoveryManager"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url')

        if not youtube_url:
            return jsonify({'error': 'YouTube URL required'}), 400

        # Use EnhancedRecoveryManager to create a session
        user_id = active_sessions[session_id]['user_data']['id']
        recovery_session_id = recovery_manager.create_recovery_session(user_id, youtube_url)
        
        # Start identification process
        # In a real environment, this might be async. For now, we do it inline.
        identification_result = recovery_manager.identify_video(recovery_session_id)

        return jsonify({
            'recovery_id': recovery_session_id,
            'youtube_url': youtube_url,
            'status': 'identified',
            'video_info': identification_result.get('video_info', {}),
            'message': 'Video identified'
        })

    except Exception as e:
        print(f"[EXCEPTION] Recovery start error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/confirm', methods=['POST'])
def confirm_recovery():
    """Confirm and process recovery"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        recovery_session_id = data.get('recovery_session_id')
        confirmed = data.get('confirmed', False)

        if not recovery_session_id:
            return jsonify({'error': 'Recovery session ID required'}), 400

        result = recovery_manager.confirm_recovery(recovery_session_id, confirmed)
        
        if confirmed and result['status'] == 'confirmed':
            # Simulate the rest of the flow for now
            recovery_manager.download_video(recovery_session_id)
            decode_result = recovery_manager.decode_video(recovery_session_id)
            return jsonify(decode_result)

        return jsonify(result)

    except Exception as e:
        print(f"[EXCEPTION] Recovery confirm error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    """Get user files from database"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    files = db.list_files()

    return jsonify({
        'files': files,
        'total_count': len(files)
    })

@app.route('/api/search', methods=['POST'])
def search_files():
    """Search files in database"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        query = data.get('query', '').lower()

        if not query:
            return jsonify({'error': 'Search query required'}), 400

        all_files = db.list_files()
        results = [f for f in all_files if query in f.get('file_name', '').lower()]

        return jsonify({
            'query': query,
            'results': results,
            'total_count': len(results)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get real user analytics"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    all_files = db.list_files()
    total_size_bytes = sum(f.get('file_size', 0) for f in all_files)
    
    # Simple size formatter
    def format_size(size_bytes):
        if size_bytes == 0: return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return "%s %s" % (s, size_name[i])

    import math

    return jsonify({
        'total_files': len(all_files),
        'total_size': format_size(total_size_bytes),
        'uploads_this_month': len(all_files), # simplified
        'recoveries_this_month': 0,
        'storage_used': format_size(total_size_bytes),
        'storage_limit': '10 GB'
    })

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
