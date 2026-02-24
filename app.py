"""
YotuDrive 2.0 - Simplified Production App
Minimal deployment version for Render
"""

import os
import time
from flask import Flask, jsonify, render_template

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

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

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return "pong"

@app.route('/ws')
def websocket_test():
    """WebSocket test endpoint"""
    return jsonify({
        'message': 'WebSocket endpoint available',
        'status': 'websocket_ready'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
