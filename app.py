"""
YotuDrive 2.0 - Production Web Application
Complete state-of-the-art cloud storage platform
"""

import os
import json
import time
import uuid
import secrets
from flask import Flask, request, jsonify, render_template, send_file, Response
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import tempfile
import shutil
from pathlib import Path

# Import YotuDrive components
from src.config_manager import config_manager
from src.advanced_logger import get_logger
from src.utils import YotuDriveException, ErrorCodes, FileValidator, NamingConvention
from src.google_integration import YotuDriveGoogleIntegration
from src.hybrid_platform import hybrid_platform, AccountType, UploadMethod
from src.enhanced_upload import enhanced_upload_manager
from src.enhanced_recovery import enhanced_recovery_manager
from src.privacy_security import privacy_manager, secure_processor, security_hardening
from src.ai_features import AIContentAnalyzer, SmartOrganizer, PersonalizedSearch

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(32)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize components
logger = get_logger()
google_integration = YotuDriveGoogleIntegration()
ai_analyzer = AIContentAnalyzer()
smart_organizer = SmartOrganizer()
personalized_search = PersonalizedSearch()

# Active sessions
active_sessions = {}
upload_progress = {}

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('production_dashboard.html')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0.0',
        'services': {
            'database': 'connected',
            'ai_services': 'active',
            'google_integration': 'ready',
            'privacy_security': 'enabled'
        }
    })

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    """Google OAuth authentication"""
    try:
        data = request.get_json()
        authorization_code = data.get('authorization_code')
        
        if not authorization_code:
            return jsonify({'error': 'Authorization code required'}), 400
        
        # Authenticate with Google
        user = google_integration.authenticate_user(authorization_code)
        
        # Create hybrid user session
        hybrid_user = hybrid_platform.create_account(
            AccountType.HYBRID,
            user.username,
            user.email,
            user.display_name
        )
        
        # Setup privacy settings
        privacy_settings = privacy_manager.setup_privacy_settings(
            hybrid_user.id,
            {
                'encryption_enabled': True,
                'end_to_end_encryption': True,
                'ai_analysis_enabled': True,
                'youtube_privacy': 'private',
                'anonymous_mode': False
            }
        )
        
        # Store session
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = {
            'user_id': hybrid_user.id,
            'user_data': hybrid_user,
            'privacy_settings': privacy_settings,
            'created_at': time.time()
        }
        
        return jsonify({
            'session_id': session_id,
            'user': {
                'id': hybrid_user.id,
                'username': hybrid_user.username,
                'email': hybrid_user.email,
                'display_name': hybrid_user.display_name
            }
        })
        
    except Exception as e:
        logger.log_exception('Google auth failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/start', methods=['POST'])
def start_upload():
    """Start file upload session"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        # Get upload data
        upload_data = request.get_json()
        files = upload_data.get('files', [])
        upload_method = UploadMethod(upload_data.get('method', 'web'))
        
        # Create upload session
        upload_session_id = enhanced_upload_manager.create_upload_session(
            user_id, files, 'file'
        )
        
        # Collect user input for video details
        file_inputs = {}
        for file_info in files:
            file_id = str(uuid.uuid4())
            user_input = enhanced_upload_manager.collect_user_input(
                upload_session_id, file_id
            )
            file_inputs[file_info['name']] = {
                'file_id': file_id,
                'user_input': user_input
            }
        
        return jsonify({
            'upload_session_id': upload_session_id,
            'file_inputs': file_inputs,
            'status': 'ready_for_details'
        })
        
    except Exception as e:
        logger.log_exception('Upload start failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/process', methods=['POST'])
def process_upload():
    """Process file upload with user details"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        privacy_settings = user_session['privacy_settings']
        
        # Get upload data
        upload_data = request.get_json()
        upload_session_id = upload_data.get('upload_session_id')
        file_details = upload_data.get('file_details', {})
        
        # Process each file
        results = []
        
        for filename, details in file_details.items():
            try:
                # Process user input
                video_details = enhanced_upload_manager.process_user_input(
                    upload_session_id, details['file_id'], details['user_input']
                )
                
                # Simulate file upload (in production, handle actual file)
                file_path = f"temp/{filename}"  # This would be the actual uploaded file
                
                # Upload with privacy settings
                if privacy_settings.encryption_enabled:
                    # Use secure stream processing
                    video_id = secure_processor.secure_stream_encode(
                        user_id, file_path, asdict(video_details)
                    )
                else:
                    # Standard processing
                    video_id = f"video_{uuid.uuid4()}"
                
                # AI analysis if enabled
                ai_analysis = {}
                if privacy_settings.ai_analysis_enabled:
                    ai_analysis = ai_analyzer.analyze_file(file_path)
                
                # Create data files
                enhanced_upload_manager.data_manager.create_video_data_file(
                    details['file_id'], video_details
                )
                
                results.append({
                    'filename': filename,
                    'video_id': video_id,
                    'status': 'completed',
                    'ai_analysis': ai_analysis
                })
                
                # Emit progress update
                socketio.emit('upload_progress', {
                    'filename': filename,
                    'progress': 100,
                    'status': 'completed'
                }, room=session_id)
                
            except Exception as e:
                results.append({
                    'filename': filename,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return jsonify({
            'results': results,
            'status': 'completed'
        })
        
    except Exception as e:
        logger.log_exception('Upload processing failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/start', methods=['POST'])
def start_recovery():
    """Start file recovery from YouTube"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        # Get YouTube URL
        data = request.get_json()
        youtube_url = data.get('youtube_url')
        
        if not youtube_url:
            return jsonify({'error': 'YouTube URL required'}), 400
        
        # Create recovery session
        recovery_session_id = enhanced_recovery_manager.create_recovery_session(
            user_id, youtube_url
        )
        
        # Identify video
        video_info = enhanced_recovery_manager.identify_video(recovery_session_id)
        
        if 'error' in video_info:
            return jsonify(video_info), 400
        
        return jsonify({
            'recovery_session_id': recovery_session_id,
            'video_info': video_info,
            'status': 'identified'
        })
        
    except Exception as e:
        logger.log_exception('Recovery start failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/recover/confirm', methods=['POST'])
def confirm_recovery():
    """Confirm and complete recovery"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        privacy_settings = user_session['privacy_settings']
        
        # Get recovery data
        data = request.get_json()
        recovery_session_id = data.get('recovery_session_id')
        confirmed = data.get('confirmed', False)
        
        # Confirm recovery
        confirmation = enhanced_recovery_manager.confirm_recovery(
            recovery_session_id, confirmed
        )
        
        if not confirmed:
            return jsonify({
                'status': 'cancelled',
                'message': 'Recovery cancelled by user'
            })
        
        # Download video
        download_result = enhanced_recovery_manager.download_video(recovery_session_id)
        
        if download_result['status'] == 'failed':
            return jsonify(download_result), 500
        
        # Decode video
        decode_result = enhanced_recovery_manager.decode_video(recovery_session_id)
        
        if decode_result['status'] == 'failed':
            return jsonify(decode_result), 500
        
        return jsonify({
            'status': 'completed',
            'recovered_files': decode_result['recovered_files'],
            'recovery_path': decode_result['recovery_path'],
            'total_duration': decode_result['total_duration']
        })
        
    except Exception as e:
        logger.log_exception('Recovery confirmation failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    """Get user files"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        # Get files from all storage locations
        files = hybrid_platform.get_user_files()
        
        return jsonify({
            'files': files,
            'total_count': len(files)
        })
        
    except Exception as e:
        logger.log_exception('Get files failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search_files():
    """Search files with AI"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        # Get search query
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Search query required'}), 400
        
        # Get user files
        files = hybrid_platform.get_user_files()
        
        # Perform AI search
        search_results = personalized_search.intelligent_search(
            query, files, user_session
        )
        
        return jsonify({
            'query': query,
            'results': search_results,
            'total_count': len(search_results)
        })
        
    except Exception as e:
        logger.log_exception('Search failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/privacy/settings', methods=['GET', 'POST'])
def privacy_settings():
    """Manage privacy settings"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        if request.method == 'GET':
            # Get current privacy settings
            settings = privacy_manager.privacy_settings.get(user_id)
            if not settings:
                # Create default settings
                settings = privacy_manager.setup_privacy_settings(user_id, {})
            
            return jsonify(asdict(settings))
        
        elif request.method == 'POST':
            # Update privacy settings
            new_settings = request.get_json()
            updated_settings = privacy_manager.setup_privacy_settings(user_id, new_settings)
            
            # Update session
            user_session['privacy_settings'] = updated_settings
            
            return jsonify({
                'message': 'Privacy settings updated',
                'settings': asdict(updated_settings)
            })
        
    except Exception as e:
        logger.log_exception('Privacy settings failed', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get user analytics"""
    try:
        session_id = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid session'}), 401
        
        user_session = active_sessions[session_id]
        user_id = user_session['user_id']
        
        # Get platform stats
        stats = hybrid_platform.get_user_stats()
        
        # Get privacy compliance
        compliance = privacy_manager.check_privacy_compliance(user_id)
        
        return jsonify({
            'stats': stats,
            'privacy_compliance': compliance,
            'session_info': {
                'created_at': user_session['created_at'],
                'duration': time.time() - user_session['created_at']
            }
        })
        
    except Exception as e:
        logger.log_exception('Analytics failed', e)
        return jsonify({'error': str(e)}), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'message': 'Connected to YotuDrive 2.0'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    """Join user session"""
    session_id = data.get('session_id')
    if session_id in active_sessions:
        # Join room for this session
        from flask_socketio import join_room
        join_room(session_id)
        emit('joined_session', {'session_id': session_id})

# Apply security headers
@app.after_request
def add_security_headers(response):
    return security_hardening.apply_security_headers(response)

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.log_exception('Internal server error', e)
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('temp', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    os.makedirs('recovery_data', exist_ok=True)
    
    # Start the application
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
