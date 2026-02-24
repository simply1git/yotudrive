"""
YotuDrive 2.0 - Modern Web Application
State-of-the-art cloud storage interface
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import os
import json
import uuid
from datetime import datetime
from src.advanced_db import database
from src.config_manager import config_manager
from src.health_monitor import run_health_check
from src.utils import FileValidator, NamingConvention
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

class YotuDriveAPI:
    """Modern API for YotuDrive 2.0"""
    
    def __init__(self):
        self.active_uploads = {}
        self.active_downloads = {}
        self.user_sessions = {}
        self.analytics = {
            'uploads_today': 0,
            'downloads_today': 0,
            'active_users': 0,
            'storage_used': 0
        }
    
    def get_dashboard_data(self):
        """Get comprehensive dashboard data"""
        health = run_health_check()
        db_stats = database.get_statistics()
        
        return {
            'health': {
                'status': health.status,
                'cpu_usage': health.checks.get('system', {}).get('cpu_percent', 0),
                'memory_usage': health.checks.get('system', {}).get('memory_percent', 0),
                'disk_usage': health.checks.get('disk_space', {}).get('directories', {}).get('.', {}).get('used_percent', 0)
            },
            'storage': {
                'total_files': db_stats['active_files'],
                'total_size': db_stats['total_size_bytes'],
                'total_size_human': db_stats['total_size_human'],
                'backups': db_stats['backups_count']
            },
            'analytics': self.analytics,
            'recent_activity': self.get_recent_activity(),
            'recommendations': health.recommendations
        }
    
    def get_recent_activity(self):
        """Get recent user activity"""
        # Mock recent activity - in real app, this would come from activity logs
        return [
            {'type': 'upload', 'file': 'presentation.pdf', 'time': '2 hours ago', 'user': 'John Doe'},
            {'type': 'download', 'file': 'video.mp4', 'time': '3 hours ago', 'user': 'Jane Smith'},
            {'type': 'share', 'file': 'document.docx', 'time': '5 hours ago', 'user': 'Bob Johnson'}
        ]
    
    def upload_file(self, file_data, metadata):
        """Modern file upload with progress tracking"""
        upload_id = str(uuid.uuid4())
        
        # Validate file
        try:
            file_path, file_size = FileValidator.validate_file(file_data['path'])
        except Exception as e:
            return {'error': str(e)}
        
        # Start upload process
        upload_info = {
            'id': upload_id,
            'filename': metadata['filename'],
            'size': file_size,
            'progress': 0,
            'status': 'uploading',
            'started_at': time.time(),
            'estimated_completion': time.time() + 60  # Estimate
        }
        
        self.active_uploads[upload_id] = upload_info
        self.analytics['uploads_today'] += 1
        
        # Start background upload
        threading.Thread(target=self._process_upload, args=(upload_id, file_data, metadata)).start()
        
        return upload_info
    
    def _process_upload(self, upload_id, file_data, metadata):
        """Background upload processing"""
        try:
            # Simulate upload progress
            for progress in range(0, 101, 5):
                if upload_id in self.active_uploads:
                    self.active_uploads[upload_id]['progress'] = progress
                    socketio.emit('upload_progress', {
                        'upload_id': upload_id,
                        'progress': progress
                    })
                    time.sleep(0.1)  # Simulate processing time
            
            # Complete upload
            if upload_id in self.active_uploads:
                self.active_uploads[upload_id]['status'] = 'completed'
                self.active_uploads[upload_id]['completed_at'] = time.time()
                
                socketio.emit('upload_complete', {
                    'upload_id': upload_id,
                    'video_url': f'https://youtube.com/watch?v=dQw4w9WgXcQ'  # Mock
                })
                
        except Exception as e:
            if upload_id in self.active_uploads:
                self.active_uploads[upload_id]['status'] = 'error'
                self.active_uploads[upload_id]['error'] = str(e)
                
                socketio.emit('upload_error', {
                    'upload_id': upload_id,
                    'error': str(e)
                })
    
    def get_file_preview(self, file_id):
        """Generate file preview"""
        file_entry = database.get_file(file_id)
        if not file_entry:
            return None
        
        # Generate preview based on file type
        preview_type = self._get_preview_type(file_entry.file_name)
        
        return {
            'type': preview_type,
            'url': f'/preview/{file_id}',
            'metadata': {
                'size': file_entry.file_size,
                'upload_date': file_entry.upload_date,
                'tags': file_entry.tags
            }
        }
    
    def _get_preview_type(self, filename):
        """Determine preview type based on filename"""
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return 'image'
        elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
            return 'video'
        elif ext in ['.mp3', '.wav', '.flac', '.aac']:
            return 'audio'
        elif ext in ['.pdf', '.doc', '.docx', '.txt']:
            return 'document'
        else:
            return 'file'

# Initialize API
api = YotuDriveAPI()

@app.route('/')
def index():
    """Modern dashboard"""
    return render_template('dashboard.html')

@app.route('/api/dashboard')
def api_dashboard():
    """Dashboard API endpoint"""
    return jsonify(api.get_dashboard_data())

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """File upload API"""
    data = request.json
    return jsonify(api.upload_file(data['file'], data['metadata']))

@app.route('/api/files')
def api_files():
    """Get files list with modern filtering"""
    files = database.list_files()
    
    # Add preview information
    enhanced_files = []
    for file_entry in files:
        file_dict = {
            'id': file_entry.id,
            'name': file_entry.file_name,
            'size': file_entry.file_size,
            'size_human': f"{file_entry.file_size / (1024*1024):.1f} MB",
            'upload_date': file_entry.upload_date,
            'video_id': file_entry.video_id,
            'tags': file_entry.tags,
            'status': file_entry.status,
            'preview': api.get_file_preview(file_entry.id)
        }
        enhanced_files.append(file_dict)
    
    return jsonify(enhanced_files)

@app.route('/api/search')
def api_search():
    """Advanced search API"""
    query = request.args.get('q', '')
    filters = request.args.get('filters', '{}')
    
    try:
        filters_dict = json.loads(filters)
    except:
        filters_dict = {}
    
    # Search files
    results = database.find_files(**filters_dict)
    
    # Format results
    search_results = []
    for file_entry in results:
        search_results.append({
            'id': file_entry.id,
            'name': file_entry.file_name,
            'size': file_entry.file_size,
            'upload_date': file_entry.upload_date,
            'tags': file_entry.tags,
            'relevance': self._calculate_relevance(file_entry, query)
        })
    
    # Sort by relevance
    search_results.sort(key=lambda x: x['relevance'], reverse=True)
    
    return jsonify(search_results)

def _calculate_relevance(self, file_entry, query):
    """Calculate search relevance score"""
    score = 0
    query_lower = query.lower()
    
    # Name match
    if query_lower in file_entry.file_name.lower():
        score += 10
    
    # Tag match
    for tag in file_entry.tags:
        if query_lower in tag.lower():
            score += 5
    
    # Metadata match
    for key, value in file_entry.metadata.items():
        if query_lower in str(value).lower():
            score += 3
    
    return score

@app.route('/api/analytics')
def api_analytics():
    """Analytics API"""
    return jsonify({
        'uploads_today': api.analytics['uploads_today'],
        'downloads_today': api.analytics['downloads_today'],
        'active_users': api.analytics['active_users'],
        'storage_used': api.analytics['storage_used'],
        'trends': {
            'uploads_last_7_days': [5, 8, 12, 7, 15, 9, 11],
            'storage_growth': [100, 150, 200, 180, 250, 300, 350]
        }
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    api.analytics['active_users'] += 1
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")
    api.analytics['active_users'] = max(0, api.analytics['active_users'] - 1)

@socketio.on('upload_progress_request')
def handle_upload_progress_request(data):
    """Handle upload progress request"""
    upload_id = data.get('upload_id')
    if upload_id in api.active_uploads:
        emit('upload_progress', api.active_uploads[upload_id])

if __name__ == '__main__':
    print("🚀 Starting YotuDrive 2.0 - Modern Web Interface")
    print("📱 Open http://localhost:5000 in your browser")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
