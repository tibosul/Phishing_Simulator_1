import re
import hashlib
import secrets
import string
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from flask import request, current_app
import logging


def generate_unique_id(length=16):
    """
    Generează un ID unic pentru tracking
    
    Args:
        length: Lungimea ID-ului generat
        
    Returns:
        str: ID unic alfanumeric
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_uuid():
    """
    Generează un UUID4 standard
    
    Returns:
        str: UUID în format string
    """
    return str(uuid.uuid4())


def generate_tracking_token():
    """
    Generează un token special pentru tracking links
    
    Returns:
        str: Token de tracking sigur
    """
    return secrets.token_urlsafe(32)


def hash_password(password):
    """
    Hash pentru parole (deși în phishing le stocăm în clar pentru demonstrație)
    
    Args:
        password: Parola de hash-uit
        
    Returns:
        str: Hash-ul parolei
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def generate_secure_filename(filename):
    """
    Generează un nume de fișier sigur
    
    Args:
        filename: Numele original al fișierului
        
    Returns:
        str: Nume de fișier securizat
    """
    # Păstrează doar caractere alfanumerice și puncte
    filename = re.sub(r'[^a-zA-Z0-9.]', '_', filename)
    
    # Adaugă timestamp pentru unicitate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    
    return f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"


def sanitize_input(text):
    """
    Sanitizează input-ul utilizatorului
    
    Args:
        text: Textul de sanitizat
        
    Returns:
        str: Text sanitizat
    """
    if not text:
        return ""
    
    # Elimină caractere periculoase
    text = re.sub(r'[<>"\']', '', str(text))
    
    # Limitează lungimea
    text = text[:1000]
    
    return text.strip()


def format_datetime(dt, format_str="%Y-%m-%d %H:%M:%S"):
    """
    Formatează un obiect datetime
    
    Args:
        dt: Obiectul datetime
        format_str: Formatul dorit
        
    Returns:
        str: Data formatată
    """
    if not dt:
        return ""
    
    return dt.strftime(format_str)


def time_ago(dt):
    """
    Returnează timpul trecut de la o dată (ex: "2 hours ago")
    
    Args:
        dt: Obiectul datetime
        
    Returns:
        str: Timpul trecut în format human-readable
    """
    if not dt:
        return "Unknown"
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"


def get_client_ip():
    """
    Obține IP-ul real al clientului (ținând cont de proxy-uri)
    
    Returns:
        str: Adresa IP a clientului
    """
    try:
        if request and request.headers.getlist("X-Forwarded-For"):
            ip = request.headers.getlist("X-Forwarded-For")[0]
        elif request and request.headers.get("X-Real-IP"):
            ip = request.headers.get("X-Real-IP")
        elif request:
            ip = request.remote_addr
        else:
            ip = None
        
        return ip or "Unknown"
    except RuntimeError:
        # Outside of request context (e.g., in tests)
        return "127.0.0.1"


def get_user_agent():
    """
    Obține User-Agent-ul clientului
    
    Returns:
        str: User-Agent string
    """
    try:
        return request.headers.get('User-Agent', 'Unknown') if request else 'Test-Agent'
    except RuntimeError:
        # Outside of request context (e.g., in tests)
        return "Test-Agent"


def is_safe_url(target):
    """
    Verifică dacă un URL este sigur pentru redirect
    
    Args:
        target: URL-ul de verificat
        
    Returns:
        bool: True dacă URL-ul este sigur
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def build_tracking_url(campaign_id, target_id, page='login'):
    """
    Construiește URL-ul cu tracking pentru phishing
    
    Args:
        campaign_id: ID-ul campaniei
        target_id: ID-ul țintei
        page: Pagina destinație (login, register, etc.)
        
    Returns:
        str: URL complet cu parametri de tracking
    """
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    tracking_token = generate_tracking_token()
    
    url = f"{base_url}/revolut/{page}?c={campaign_id}&t={target_id}&token={tracking_token}"
    
    return url


def build_tracking_pixel_url(campaign_id, target_id):
    """
    Construiește URL-ul pentru pixel-ul de tracking (deschiderea email-urilor)
    
    Args:
        campaign_id: ID-ul campaniei
        target_id: ID-ul țintei
        
    Returns:
        str: URL pentru tracking pixel
    """
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
    tracking_token = generate_tracking_token()
    
    url = f"{base_url}/webhook/pixel.gif?c={campaign_id}&t={target_id}&token={tracking_token}"
    
    return url


def parse_csv_line(line, delimiter=','):
    """
    Parsează o linie CSV manual (pentru cazuri simple)
    
    Args:
        line: Linia CSV
        delimiter: Delimitatorul folosit
        
    Returns:
        list: Lista cu valorile parsate
    """
    return [field.strip().strip('"') for field in line.split(delimiter)]


def validate_campaign_data(data):
    """
    Validează datele unei campanii
    
    Args:
        data: Dicționarul cu datele campaniei
        
    Returns:
        tuple: (is_valid, error_message)
    """
    required_fields = ['name', 'type']
    
    for field in required_fields:
        if not data.get(field):
            return False, f"Field '{field}' is required"
    
    if data['type'] not in ['email', 'sms', 'both']:
        return False, "Type must be 'email', 'sms', or 'both'"
    
    if len(data['name']) < 3:
        return False, "Campaign name must be at least 3 characters"
    
    return True, ""


def generate_random_user_agent():
    """
    Generează un User-Agent random pentru a simula trafic real
    
    Returns:
        str: User-Agent string
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
    ]
    
    return secrets.choice(user_agents)


def log_security_event(event_type, details, ip_address=None):
    """
    Loggează evenimente de securitate
    
    Args:
        event_type: Tipul evenimentului
        details: Detaliile evenimentului
        ip_address: IP-ul de unde vine evenimentul
    """
    if not ip_address:
        ip_address = get_client_ip()
    
    timestamp = datetime.utcnow().isoformat()
    
    log_entry = f"[SECURITY] {timestamp} | {event_type} | IP: {ip_address} | {details}"
    
    logging.warning(log_entry)


def create_pagination_info(page, per_page, total):
    """
    Creează informații pentru paginare
    
    Args:
        page: Pagina curentă
        per_page: Elemente per pagină
        total: Total elemente
        
    Returns:
        dict: Informații despre paginare
    """
    total_pages = (total + per_page - 1) // per_page
    
    return {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None
    }


def mask_sensitive_data(data, fields=['password', 'token', 'key']):
    """
    Maskează date sensibile pentru logging
    
    Args:
        data: Datele de mascat
        fields: Lista cu câmpurile sensibile
        
    Returns:
        dict: Date cu câmpurile sensibile mascate
    """
    if isinstance(data, dict):
        masked = data.copy()
        for field in fields:
            if field in masked:
                masked[field] = "*" * 8
        return masked
    
    return data