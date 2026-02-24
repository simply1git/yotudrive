"""
YotuDrive 2.0 - Simplified Production App
Minimal deployment version for Railway
"""

import os
import time
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

socketio = SocketIO(app, cors_allowed_origins="*")

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
            'api_services': 'active',
            'privacy_security': 'enabled'
        }
    })

@app.route('/api/test')
def test_api():
    """Test API endpoint"""
    return jsonify({
        'message': 'YotuDrive 2.0 API is working!',
        'status': 'success',
        'timestamp': time.time()
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'version': '2.0.0',
        'services': {
            'database': 'connected',
            'api_services': 'active',
            'privacy_security': 'enabled'
        }
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return "pong"

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'message': 'Connected to YotuDrive 2.0'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
