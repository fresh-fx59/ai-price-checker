#!/usr/bin/env python3
"""
Simple webhook server for automatic deployments
Run this on your server to enable automatic deployments on git push
"""

import os
import subprocess
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your-webhook-secret-here')
DEPLOY_SCRIPT = '/opt/price-monitor/deploy.sh'

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle GitHub webhook for automatic deployment"""
    
    # Verify webhook signature
    signature = request.headers.get('X-Hub-Signature-256')
    if signature:
        expected_signature = 'sha256=' + hmac.new(
            WEBHOOK_SECRET.encode(),
            request.data,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid signature'}), 403
    
    # Check if this is a push to main branch
    payload = request.json
    if payload.get('ref') == 'refs/heads/main':
        try:
            # Run deployment script
            result = subprocess.run([DEPLOY_SCRIPT], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=300)
            
            if result.returncode == 0:
                return jsonify({
                    'status': 'success',
                    'message': 'Deployment completed successfully',
                    'output': result.stdout
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Deployment failed',
                    'error': result.stderr
                }), 500
                
        except subprocess.TimeoutExpired:
            return jsonify({
                'status': 'error',
                'message': 'Deployment timed out'
            }), 500
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Deployment error: {str(e)}'
            }), 500
    
    return jsonify({'status': 'ignored', 'message': 'Not a main branch push'})

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=9000, debug=False)