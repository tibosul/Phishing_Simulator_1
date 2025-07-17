import re
import dns.resolver
from urllib.parse import urlparse
from datetime import datetime
import logging
from functools import wraps
from flask import request, jsonify


class ValidationError(Exception):
    """Excepție pentru erorile de validare"""
    pass


def validate_email(email):
    """
    Validează o adresă de email cu validări RFC-compliant și securizate
    
    Args:
        email: Adresa de email de validat
        
    Returns:
        bool: True dacă email-ul este valid
        
    Raises:
        ValidationError: Dacă email-ul nu este valid
    """
    if not email:
        raise ValidationError("Email address is required")
    
    # Strip whitespace
    email = email.strip()
    
    # Pattern pentru validarea email-ului (enhanced)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        raise ValidationError("Invalid email format")
    
    # Verifică lungimea
    if len(email) > 254:
        raise ValidationError("Email address too long")
    
    # Verifică partea locală (înainte de @)
    local_part = email.split('@')[0]
    if len(local_part) > 64:
        raise ValidationError("Email local part too long")
    
    # Verifică pentru double dots (consecutive dots)
    if '..' in email:
        raise ValidationError("Email contains consecutive dots")
    
    # Verifică că nu începe sau se termină cu punct
    if local_part.startswith('.') or local_part.endswith('.'):
        raise ValidationError("Email local part cannot start or end with dot")
    
    # Verifică domeniul
    domain_part = email.split('@')[1]
    if domain_part.startswith('.') or domain_part.endswith('.'):
        raise ValidationError("Email domain cannot start or end with dot")
    
    if '..' in domain_part:
        raise ValidationError("Email domain contains consecutive dots")
    
    return True


def validate_email_with_dns(email):
    """
    Validează email cu verificare DNS (opțional, pentru cazuri speciale)
    
    Args:
        email: Adresa de email
        
    Returns:
        bool: True dacă email-ul și domeniul sunt valide
    """
    try:
        # Validare de bază
        validate_email(email)
        
        # Extrage domeniul
        domain = email.split('@')[1]
        
        # Verifică înregistrările MX
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            return len(mx_records) > 0
        except:
            # Dacă nu găsește MX, încearcă A record
            try:
                dns.resolver.resolve(domain, 'A')
                return True
            except:
                raise ValidationError(f"Domain {domain} does not exist")
                
    except ValidationError:
        raise
    except Exception as e:
        logging.warning(f"DNS validation failed for {email}: {str(e)}")
        return True  # Fall back to basic validation


def validate_phone_number(phone):
    """
    Validează un număr de telefon
    
    Args:
        phone: Numărul de telefon
        
    Returns:
        bool: True dacă numărul este valid
        
    Raises:
        ValidationError: Dacă numărul nu este valid
    """
    if not phone:
        raise ValidationError("Phone number is required")
    
    # Elimină spațiile și caracterele speciale
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Verifică format internațional (+40...)
    international_pattern = r'^\+[1-9]\d{1,14}$'
    
    # Verifică format național (07...)
    national_pattern = r'^0[67]\d{8}$'
    
    if re.match(international_pattern, clean_phone):
        return True
    elif re.match(national_pattern, clean_phone):
        return True
    else:
        raise ValidationError("Invalid phone number format")


def validate_url(url):
    """
    Validează un URL
    
    Args:
        url: URL-ul de validat
        
    Returns:
        bool: True dacă URL-ul este valid
        
    Raises:
        ValidationError: Dacă URL-ul nu este valid
    """
    if not url:
        raise ValidationError("URL is required")
    
    try:
        result = urlparse(url)
        
        # Verifică schema
        if result.scheme not in ['http', 'https']:
            raise ValidationError("URL must use http or https scheme")
        
        # Verifică domeniul
        if not result.netloc:
            raise ValidationError("Invalid URL format")
        
        return True
        
    except Exception as e:
        raise ValidationError(f"Invalid URL: {str(e)}")


def validate_campaign_name(name):
    """
    Validează numele unei campanii
    
    Args:
        name: Numele campaniei
        
    Returns:
        bool: True dacă numele este valid
        
    Raises:
        ValidationError: Dacă numele nu este valid
    """
    if not name:
        raise ValidationError("Campaign name is required")
    
    # Elimină spațiile
    name = name.strip()
    
    if len(name) < 3:
        raise ValidationError("Campaign name must be at least 3 characters")
    
    if len(name) > 100:
        raise ValidationError("Campaign name too long (max 100 characters)")
    
    # Verifică caracterele permise
    if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', name):
        raise ValidationError("Campaign name contains invalid characters")
    
    return True


def validate_template_content(content, template_type):
    """
    Validează conținutul unui template
    
    Args:
        content: Conținutul template-ului
        template_type: Tipul template-ului (email/sms)
        
    Returns:
        bool: True dacă conținutul este valid
        
    Raises:
        ValidationError: Dacă conținutul nu este valid
    """
    if not content:
        raise ValidationError("Template content is required")
    
    if template_type == 'email':
        # Pentru email, verifică lungimea
        if len(content) > 10000:
            raise ValidationError("Email template too long")
        
        # Verifică dacă conține placeholder-uri necesare
        required_placeholders = ['{{tracking_link}}']
        for placeholder in required_placeholders:
            if placeholder not in content:
                logging.warning(f"Template missing placeholder: {placeholder}")
    
    elif template_type == 'sms':
        # Pentru SMS, verifică lungimea
        if len(content) > 160:
            raise ValidationError("SMS template too long (max 160 characters)")
        
        # Verifică dacă conține link
        if '{{tracking_link}}' not in content:
            raise ValidationError("SMS template must contain tracking link")
    
    return True


def validate_file_upload(file, allowed_extensions=None, max_size=None):
    """
    Validează un fișier uplodat
    
    Args:
        file: Fișierul de validat
        allowed_extensions: Lista cu extensiile permise
        max_size: Mărimea maximă în bytes
        
    Returns:
        bool: True dacă fișierul este valid
        
    Raises:
        ValidationError: Dacă fișierul nu este valid
    """
    if not file:
        raise ValidationError("No file provided")
    
    if not file.filename:
        raise ValidationError("No file selected")
    
    # Verifică extensia
    if allowed_extensions:
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in allowed_extensions:
            raise ValidationError(f"File type not allowed. Allowed: {', '.join(allowed_extensions)}")
    
    # Verifică mărimea
    if max_size:
        file.seek(0, 2)  # Merge la sfârșitul fișierului
        file_size = file.tell()
        file.seek(0)  # Întoarce la început
        
        if file_size > max_size:
            raise ValidationError(f"File too large. Max size: {max_size / 1024 / 1024:.1f}MB")
    
    return True


def validate_csv_format(file_content, required_columns=None, max_rows=None, max_file_size=None):
    """
    Validează formatul unui fișier CSV cu limite de securitate
    
    Args:
        file_content: Conținutul fișierului CSV
        required_columns: Lista cu coloanele obligatorii
        max_rows: Numărul maxim de rânduri permise (default: 10000)
        max_file_size: Mărimea maximă a fișierului în bytes (default: 5MB)
        
    Returns:
        bool: True dacă CSV-ul este valid
        
    Raises:
        ValidationError: Dacă CSV-ul nu este valid sau depășește limitele
    """
    if not file_content:
        raise ValidationError("CSV file is empty")
    
    # Verifică mărimea fișierului pentru prevenirea atacurilor DoS
    if max_file_size is None:
        max_file_size = 5 * 1024 * 1024  # 5MB default
    
    file_size = len(file_content.encode('utf-8'))
    if file_size > max_file_size:
        raise ValidationError(f"CSV file too large. Maximum size: {max_file_size / 1024 / 1024:.1f}MB")
    
    lines = file_content.strip().split('\n')
    
    if len(lines) < 2:
        raise ValidationError("CSV must have at least header and one data row")
    
    # Verifică numărul de rânduri pentru prevenirea atacurilor DoS
    if max_rows is None:
        max_rows = 10000  # 10K rows default
    
    if len(lines) - 1 > max_rows:  # -1 pentru header
        raise ValidationError(f"CSV has too many rows. Maximum allowed: {max_rows}")
    
    # Verifică header-ul
    header = lines[0].split(',')
    header = [col.strip().strip('"') for col in header]
    
    if required_columns:
        missing_columns = set(required_columns) - set(header)
        if missing_columns:
            raise ValidationError(f"Missing required columns: {', '.join(missing_columns)}")
    
    # Verifică dacă toate rândurile au același număr de coloane
    expected_cols = len(header)
    for i, line in enumerate(lines[1:], 2):
        cols = line.split(',')
        if len(cols) != expected_cols:
            raise ValidationError(f"Line {i} has wrong number of columns")
    
    return True


def validate_ip_address(ip):
    """
    Validează o adresă IP
    
    Args:
        ip: Adresa IP
        
    Returns:
        bool: True dacă IP-ul este valid
        
    Raises:
        ValidationError: Dacă IP-ul nu este valid
    """
    if not ip:
        raise ValidationError("IP address is required")
    
    # IPv4 pattern
    ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    # IPv6 pattern (simplified)
    ipv6_pattern = r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    
    if re.match(ipv4_pattern, ip) or re.match(ipv6_pattern, ip):
        return True
    else:
        raise ValidationError("Invalid IP address format")


def validate_password_strength(password):
    """
    Validează puterea unei parole (pentru interfața admin)
    
    Args:
        password: Parola de validat
        
    Returns:
        dict: Informații despre puterea parolei
        
    Raises:
        ValidationError: Dacă parola este prea slabă
    """
    if not password:
        raise ValidationError("Password is required")
    
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    
    score = 0
    feedback = []
    
    # Verifică lungimea
    if len(password) >= 12:
        score += 1
        feedback.append("Good length")
    
    # Verifică litere mari
    if re.search(r'[A-Z]', password):
        score += 1
        feedback.append("Contains uppercase")
    
    # Verifică litere mici
    if re.search(r'[a-z]', password):
        score += 1
        feedback.append("Contains lowercase")
    
    # Verifică cifre
    if re.search(r'\d', password):
        score += 1
        feedback.append("Contains numbers")
    
    # Verifică caractere speciale
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
        feedback.append("Contains special characters")
    
    strength = "Weak"
    if score >= 4:
        strength = "Strong"
    elif score >= 3:
        strength = "Medium"
    
    return {
        'score': score,
        'strength': strength,
        'feedback': feedback
    }


def sanitize_and_validate_input(data, field_validations):
    """
    Sanitizează și validează un dicționar de date
    
    Args:
        data: Datele de validat
        field_validations: Dicționar cu validările pentru fiecare câmp
        
    Returns:
        dict: Datele sanitizate și validate
        
    Raises:
        ValidationError: Dacă validarea eșuează
    """
    result = {}
    errors = []
    
    for field, value in data.items():
        try:
            # Sanitizează valoarea
            if isinstance(value, str):
                value = value.strip()
            
            # Aplică validarea specifică
            if field in field_validations:
                validator = field_validations[field]
                if callable(validator):
                    validator(value)
                
            result[field] = value
            
        except ValidationError as e:
            errors.append(f"{field}: {str(e)}")
    
    if errors:
        raise ValidationError("; ".join(errors))
    
    return result


def validate_backend_input(field_rules):
    """
    Decorator pentru validarea backend a input-urilor pe endpoint-uri
    
    Args:
        field_rules: Dicționar cu regulile de validare pentru fiecare câmp
                    Exemplu: {
                        'email': validate_email,
                        'phone': validate_phone_number,
                        'name': lambda x: validate_campaign_name(x)
                    }
    
    Returns:
        Decorated function that validates inputs before execution
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get data from request
            if request.is_json:
                data = request.get_json() or {}
            else:
                data = request.form.to_dict()
            
            errors = []
            
            # Validate each field according to rules
            for field, validator in field_rules.items():
                if field in data and data[field]:
                    try:
                        validator(data[field])
                    except ValidationError as e:
                        errors.append(f"{field}: {str(e)}")
                    except Exception as e:
                        errors.append(f"{field}: Validation error - {str(e)}")
            
            # If there are validation errors, return them
            if errors:
                if request.is_json:
                    return jsonify({'error': 'Validation failed', 'details': errors}), 400
                else:
                    # For form submissions, we'll let the original function handle the errors
                    # by adding them to a special attribute
                    request._validation_errors = errors
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_valid_email(field_name='email'):
    """
    Decorator pentru a require email valid pe endpoint
    
    Args:
        field_name: Numele câmpului de email în request
    """
    return validate_backend_input({field_name: validate_email})


def require_valid_phone(field_name='phone'):
    """
    Decorator pentru a require telefon valid pe endpoint
    
    Args:
        field_name: Numele câmpului de telefon în request
    """
    return validate_backend_input({field_name: validate_phone_number})