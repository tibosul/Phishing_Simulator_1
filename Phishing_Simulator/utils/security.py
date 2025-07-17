#!/usr/bin/env python3
"""
Security utilities for Phishing Simulator

Provides input sanitization, XSS protection, CSRF handling, 
and other security features.
"""

import re
import html
import logging
from urllib.parse import urlparse
from flask import request, current_app, session
from functools import wraps

try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    logging.warning("bleach not available, using basic HTML escaping")

# Allowed HTML tags for content that should support basic formatting
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'a', 'div', 'span'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    '*': ['class', 'id']
}

# XSS patterns to detect and block
XSS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
    r'<link[^>]*>',
    r'<meta[^>]*>',
    r'data:text/html',
    r'vbscript:',
    r'<svg[^>]*>.*?</svg>',
]


def sanitize_input(text, allow_html=False, strict=True):
    """
    Sanitize user input to prevent XSS and injection attacks
    
    Args:
        text: Input text to sanitize
        allow_html: Whether to allow safe HTML tags
        strict: Whether to apply strict sanitization rules
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return text
    
    # Convert to string if not already
    text = str(text)
    
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    if strict:
        # Check for obvious XSS patterns
        for pattern in XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logging.warning(f"Potentially malicious input detected: {pattern}")
                # For campaign names and critical fields, reject entirely
                if not allow_html:
                    raise ValueError("Input contains potentially malicious content")
    
    if allow_html and BLEACH_AVAILABLE:
        # Allow safe HTML tags with bleach
        text = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    elif allow_html:
        # Basic HTML escaping if bleach not available
        text = html.escape(text, quote=False)
        # Allow some basic tags
        text = text.replace('&lt;p&gt;', '<p>').replace('&lt;/p&gt;', '</p>')
        text = text.replace('&lt;br&gt;', '<br>')
        text = text.replace('&lt;strong&gt;', '<strong>').replace('&lt;/strong&gt;', '</strong>')
    else:
        # Full HTML escaping for non-HTML fields
        text = html.escape(text, quote=True)
    
    # Trim whitespace
    text = text.strip()
    
    return text


def validate_csrf_token():
    """
    Validate CSRF token for POST requests
    
    Returns:
        bool: True if token is valid or not required
    """
    if request.method in ['GET', 'HEAD', 'OPTIONS']:
        return True
    
    if not current_app.config.get('WTF_CSRF_ENABLED', False):
        return True
    
    token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    
    if not token:
        logging.warning(f"CSRF token missing for {request.endpoint}")
        return False
    
    # Basic token validation (in a real app, use Flask-WTF)
    expected_token = session.get('csrf_token')
    if not expected_token or token != expected_token:
        logging.warning(f"CSRF token mismatch for {request.endpoint}")
        return False
    
    return True


def require_csrf(f):
    """
    Decorator to require CSRF token validation
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not validate_csrf_token():
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def generate_csrf_token():
    """
    Generate a CSRF token for the current session
    
    Returns:
        str: CSRF token
    """
    import secrets
    
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    
    return session['csrf_token']


def is_safe_url(target):
    """
    Check if a URL is safe for redirect
    
    Args:
        target: URL to check
        
    Returns:
        bool: True if URL is safe
    """
    if not target:
        return False
    
    try:
        parsed = urlparse(target)
        
        # Only allow relative URLs or same-origin URLs
        if parsed.netloc and parsed.netloc != request.host:
            return False
        
        # Block javascript: and data: schemes
        if parsed.scheme and parsed.scheme.lower() in ['javascript', 'data', 'vbscript']:
            return False
        
        return True
    except Exception:
        return False


def validate_file_upload(file, allowed_extensions=None, max_size=None):
    """
    Validate file upload for security
    
    Args:
        file: Uploaded file object
        allowed_extensions: Set of allowed file extensions
        max_size: Maximum file size in bytes
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file or not file.filename:
        return False, "No file uploaded"
    
    filename = file.filename.lower()
    
    # Check file extension
    if allowed_extensions:
        if not any(filename.endswith('.' + ext.lower()) for ext in allowed_extensions):
            return False, f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
    
    # Check file size
    if max_size:
        file.seek(0, 2)  # Seek to end
        size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if size > max_size:
            return False, f"File too large. Maximum size: {max_size // 1024 // 1024}MB"
    
    # Basic content validation
    try:
        file.seek(0)
        content = file.read(1024)  # Read first 1KB
        file.seek(0)
        
        # Check for executable signatures
        if content.startswith(b'\x4d\x5a'):  # Windows PE
            return False, "Executable files not allowed"
        
        if content.startswith(b'\x7fELF'):  # Linux ELF
            return False, "Executable files not allowed"
        
    except Exception:
        return False, "Unable to validate file content"
    
    return True, None


def apply_security_headers(response):
    """
    Apply security headers to HTTP response
    
    Args:
        response: Flask response object
        
    Returns:
        response: Modified response with security headers
    """
    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # XSS protection (for older browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Content Security Policy (basic)
    csp = "default-src 'self'; " \
          "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; " \
          "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; " \
          "img-src 'self' data:; " \
          "font-src 'self' cdn.jsdelivr.net;"
    
    response.headers['Content-Security-Policy'] = csp
    
    # Strict Transport Security (if HTTPS)
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response


def log_security_event(event_type, description, details=None):
    """
    Log security-related events
    
    Args:
        event_type: Type of security event
        description: Event description
        details: Additional event details
    """
    try:
        from utils.helpers import get_client_ip
        ip = get_client_ip()
    except:
        ip = "Unknown"
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'description': description,
        'ip_address': ip,
        'user_agent': request.headers.get('User-Agent', 'Unknown') if request else 'System',
        'details': details
    }
    
    logging.warning(f"[SECURITY] {event_type} | IP: {ip} | {description}")
    
    # In a production environment, you might want to send this to a SIEM
    return log_entry


def rate_limit_check(key, limit=10, window=60):
    """
    Simple rate limiting check
    
    Args:
        key: Rate limit key (e.g., IP address)
        limit: Number of requests allowed
        window: Time window in seconds
        
    Returns:
        bool: True if request is allowed
    """
    # This is a simplified implementation
    # In production, use Redis or similar
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    cache_key = f"rate_limit_{key}_{window}"
    
    # Get or initialize request count
    if not hasattr(current_app, '_rate_limit_cache'):
        current_app._rate_limit_cache = {}
    
    cache = current_app._rate_limit_cache
    
    if cache_key not in cache:
        cache[cache_key] = {'count': 0, 'window_start': now}
    
    entry = cache[cache_key]
    
    # Reset window if expired
    if now - entry['window_start'] > timedelta(seconds=window):
        entry['count'] = 0
        entry['window_start'] = now
    
    # Check limit
    if entry['count'] >= limit:
        log_security_event('rate_limit_exceeded', f"Rate limit exceeded for {key}")
        return False
    
    entry['count'] += 1
    return True


def require_rate_limit(limit=10, window=60, key_func=None):
    """
    Decorator for rate limiting endpoints
    
    Args:
        limit: Number of requests allowed
        window: Time window in seconds  
        key_func: Function to generate rate limit key
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from utils.helpers import get_client_ip
                key = key_func() if key_func else get_client_ip()
            except:
                key = "unknown"
            
            if not rate_limit_check(key, limit, window):
                from flask import abort
                abort(429)  # Too Many Requests
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Import datetime for logging
from datetime import datetime