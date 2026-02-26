"""
YotuDrive 2.0 - Minimal OAuth Backend for Render
Handles Google OAuth authentication and basic API endpoints
"""

import os
import json
import time
import uuid
import secrets
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(32)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Enable CORS for frontend
CORS(app)

# Active sessions storage (in production, use Redis/database)
active_sessions = {}
upload_sessions = {}

# Google OAuth configuration (replace with your actual values)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret')
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
    """Handle Google OAuth callback"""
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Get authorization code from frontend
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
            return jsonify({'error': 'Failed to exchange authorization code'}), 400

        token_info = token_response.json()
        access_token = token_info.get('access_token')

        if not access_token:
            return jsonify({'error': 'No access token received'}), 400

        # Get user info from Google
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}

        user_response = requests.get(user_info_url, headers=headers)

        if user_response.status_code != 200:
            return jsonify({'error': 'Failed to get user info'}), 400

        user_info = user_response.json()

        # Create user session
        session_id = str(uuid.uuid4())
        user_data = {
            'id': user_info.get('id'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'verified_email': user_info.get('verified_email', False)
        }

        # Store session (in production, use database)
        active_sessions[session_id] = {
            'user_data': user_data,
            'access_token': access_token,
            'created_at': time.time(),
            'expires_at': time.time() + 3600  # 1 hour
        }

        return jsonify({
            'session_id': session_id,
            'user': user_data,
            'message': 'Login successful'
        })

    except Exception as e:
        print(f"OAuth error: {str(e)}")
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500

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
    """Process file upload"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        upload_session_id = data.get('upload_session_id')

        if not upload_session_id or upload_session_id not in upload_sessions:
            return jsonify({'error': 'Invalid upload session'}), 400

        # Simulate processing (in production, handle actual file processing)
        results = []
        for file_info in upload_sessions[upload_session_id]['files']:
            results.append({
                'filename': file_info['name'],
                'status': 'completed',
                'video_id': f"video_{uuid.uuid4()}",
                'size': file_info.get('size', 0)
            })

        # Update session status
        upload_sessions[upload_session_id]['status'] = 'completed'

        return jsonify({
            'results': results,
            'status': 'completed'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/start', methods=['POST'])
def start_recovery():
    """Start YouTube recovery"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        youtube_url = data.get('youtube_url')

        if not youtube_url:
            return jsonify({'error': 'YouTube URL required'}), 400

        # Simulate recovery process (in production, implement actual recovery)
        recovery_id = str(uuid.uuid4())

        return jsonify({
            'recovery_id': recovery_id,
            'youtube_url': youtube_url,
            'status': 'started',
            'message': 'Recovery simulation started'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    """Get user files"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    # Return mock files (in production, get from database)
    mock_files = [
        {
            'id': '1',
            'name': 'sample_video.mp4',
            'size': '10MB',
            'uploaded_at': time.time(),
            'type': 'video'
        }
    ]

    return jsonify({
        'files': mock_files,
        'total_count': len(mock_files)
    })

@app.route('/api/search', methods=['POST'])
def search_files():
    """Search files"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        query = data.get('query', '')

        if not query:
            return jsonify({'error': 'Search query required'}), 400

        # Return mock search results
        mock_results = [
            {
                'id': '1',
                'name': 'sample_video.mp4',
                'match_score': 0.95,
                'type': 'video'
            }
        ]

        return jsonify({
            'query': query,
            'results': mock_results,
            'total_count': len(mock_results)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get user analytics"""
    session_id = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Authentication required'}), 401

    # Return mock analytics
    return jsonify({
        'total_files': 5,
        'total_size': '50MB',
        'uploads_this_month': 3,
        'recoveries_this_month': 1,
        'storage_used': '25MB',
        'storage_limit': '100MB'
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
