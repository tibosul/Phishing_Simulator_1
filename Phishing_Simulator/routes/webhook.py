# ==========================================
# routes/webhook.py - STUB
# ==========================================

"""
Webhook routes - Tracking endpoints
TODO: Implementare completă
"""

from flask import Blueprint, jsonify, request

bp = Blueprint('webhook', __name__)

@bp.route('/pixel.gif')
def tracking_pixel():
    """Tracking pixel pentru email-uri - STUB"""
    campaign_id = request.args.get('c')
    target_id = request.args.get('t')
    
    print(f"STUB: Email opened - Campaign: {campaign_id}, Target: {target_id}")
    
    # Return 1x1 transparent pixel
    from flask import Response
    import base64
    
    # 1x1 transparent GIF
    pixel_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
    
    return Response(pixel_data, mimetype='image/gif')

@bp.route('/click')
def track_click():
    """Track link clicks - STUB"""
    campaign_id = request.args.get('c')
    target_id = request.args.get('t')
    
    print(f"STUB: Link clicked - Campaign: {campaign_id}, Target: {target_id}")
    
    return jsonify({'status': 'tracked'})