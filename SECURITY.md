# Security Features Documentation

## Overview

This document outlines the comprehensive security features implemented in the Phishing Simulator application to ensure safe operation and prevent misuse.

## Security Features Implemented

### 1. Backend Input Validation

**Email Validation:**
- RFC-compliant email format validation
- Length restrictions (max 254 characters)
- Domain validation support
- Applied on all endpoints that accept email input

**Phone Number Validation:**
- International format support (+country code)
- National format support (Romania: 07xx, 06xx)
- Length and character validation
- Applied on all endpoints that accept phone input

**Implementation:**
```python
# Backend validation decorators
@validate_backend_input({
    'email': validate_email,
    'phone': lambda x: validate_phone_number(x) if x else True
})
def create_target():
    # Validation happens automatically before function execution
```

### 2. CSV Upload Security

**File Size Limits:**
- Maximum file size: 5MB
- Prevents memory exhaustion attacks
- Early validation before processing

**Row Count Limits:**
- Maximum rows: 10,000
- Prevents DoS attacks through large datasets
- Double validation (before and after parsing)

**Content Validation:**
- Email validation for each row
- Phone validation when present
- Malicious content detection and sanitization

**Implementation:**
```python
# Enhanced CSV import with security limits
stats = CampaignService.add_targets_from_csv(
    campaign_id=campaign_id,
    csv_content=csv_content,
    skip_duplicates=skip_duplicates,
    max_rows=10000,  # Explicit limit
    max_file_size=5*1024*1024  # 5MB limit
)
```

### 3. Template Sanitization and XSS Prevention

**Content Sanitization:**
- Uses bleach library for HTML sanitization
- Removes dangerous HTML tags and attributes
- Allows safe formatting tags only

**Variable Validation:**
- Validates template variables ({{variable}})
- Whitelist of allowed variables
- Prevents injection through variable names

**Dangerous Pattern Detection:**
- Blocks `<script>` tags
- Blocks `javascript:` URLs
- Blocks `on*` event handlers
- Blocks `<iframe>`, `<object>`, `<embed>` tags

**Implementation:**
```python
# Template creation with security validation
try:
    validate_template_variables(content)
    content = sanitize_template_content(content, template_type)
except ValidationError as e:
    flash(f'Template security validation failed: {str(e)}', 'error')
    return render_template('admin/create_template.html')
```

### 4. Standardized API Error Handling

**Consistent Response Format:**
```json
{
    "success": false,
    "error": "Error message",
    "error_type": "validation_error",
    "details": ["Specific error 1", "Specific error 2"]
}
```

**HTTP Status Codes:**
- 400: Validation errors
- 401: Unauthorized access
- 403: Forbidden access
- 404: Resource not found
- 429: Rate limit exceeded
- 500: Server errors

**Error Types:**
- `validation_error`: Input validation failures
- `not_found`: Resource not found
- `unauthorized`: Authentication required
- `forbidden`: Access denied
- `rate_limit`: Too many requests
- `server_error`: Internal server errors

### 5. Rate Limiting

**Endpoint-Specific Limits:**
- Critical endpoints: 10 requests/hour
- General endpoints: 100 requests/hour
- Per-IP tracking

**Critical Endpoints:**
- Target creation
- Template creation
- Campaign creation
- CSV upload
- Bulk import

**Implementation:**
```python
# Automatic rate limiting in middleware
@app.before_request
def security_middleware():
    if request.endpoint in strict_endpoints:
        if not rate_limit_check(client_ip, limit=10, window=3600):
            return jsonify({'error': 'Rate limit exceeded'}), 429
```

### 6. Security Headers

**Headers Applied:**
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-XSS-Protection: 1; mode=block` - XSS protection
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` - Restricts resource loading
- `Strict-Transport-Security` - Forces HTTPS (production)

### 7. Comprehensive Security Logging

**Events Logged:**
- Admin actions (create, update, delete)
- Security violations (XSS attempts, rate limiting)
- Authentication events
- File uploads
- Failed validations

**Log Format:**
```
[SECURITY] Timestamp: 2024-01-01T10:00:00 | Event: admin_create | IP: 192.168.1.1 | Endpoint: targets.create_target | Method: POST | Details: Admin action: create target (ID: 123) - Email: user@example.com, Campaign: Test Campaign
```

**Log Levels:**
- WARNING: All security events
- ERROR: Critical security events

### 8. Package Security

**Metadata:**
- Complete setup.py with security notice
- Version information
- License and copyright
- Security disclaimer

**Dependencies:**
- All dependencies specified with versions
- Security-focused libraries (bleach for sanitization)
- Regular dependency updates recommended

## Testing

### Security Test Suite

**Validation Tests:**
- Email format validation
- Phone number validation
- CSV file limits
- Template sanitization

**XSS Prevention Tests:**
- Script tag injection
- Event handler injection
- JavaScript URL injection
- Iframe injection

**API Security Tests:**
- Error response format
- Status code validation
- Rate limiting behavior

**Run Tests:**
```bash
# Basic security validation
python test_security_basic.py

# Comprehensive security tests
python tests/test_security.py

# All tests
python tests/test_core_functionality.py
```

## Configuration

### Security Settings (config.py)

```python
# Security settings
WTF_CSRF_ENABLED = True
SECURITY_HEADERS_ENABLED = True
RATE_LIMIT_ENABLED = True
RATE_LIMIT_DEFAULT = 100  # requests per hour
RATE_LIMIT_STRICT_ENDPOINTS = 10  # for sensitive endpoints

# File upload limits
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
CSV_MAX_ROWS = 10000
CSV_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
```

### Environment Variables

```bash
# Required for production
SECRET_KEY=your-secret-key-here
MAIL_USERNAME=your-email@domain.com
MAIL_PASSWORD=your-email-password
SMS_API_KEY=your-sms-api-key

# Optional security settings
LOG_LEVEL=INFO
LOG_FILE=phishing_simulator.log
RATE_LIMIT_ENABLED=true
```

## Security Best Practices

### For Administrators

1. **Regular Updates:** Keep dependencies updated
2. **Log Monitoring:** Monitor security logs for suspicious activity
3. **Access Control:** Limit admin access to authorized personnel
4. **Backup:** Regular database backups
5. **SSL/TLS:** Use HTTPS in production

### For Deployment

1. **Environment:** Use production configuration
2. **Database:** Secure database connection strings
3. **Firewall:** Restrict network access
4. **Monitoring:** Set up log aggregation
5. **Secrets:** Use environment variables for sensitive data

### For Usage

1. **Authorization:** Only use for authorized security testing
2. **Legal Compliance:** Ensure compliance with local laws
3. **Scope:** Limit testing to owned/authorized systems
4. **Documentation:** Document all testing activities
5. **Cleanup:** Remove test data after completion

## Compliance and Legal

### Security Notice

⚠️ **IMPORTANT:** This software is designed for authorized security testing and training purposes only. Users are responsible for complying with all applicable laws and regulations. Unauthorized use of this software may violate local, state, federal, or international laws.

### Features for Compliance

1. **Audit Logging:** Complete audit trail of all actions
2. **Data Protection:** Secure handling of sensitive data
3. **Access Control:** Role-based access control
4. **Data Retention:** Configurable data retention policies
5. **Export/Import:** Data portability features

## Incident Response

### Security Event Response

1. **Detection:** Automated logging and alerting
2. **Analysis:** Log analysis and threat assessment
3. **Containment:** Rate limiting and access blocking
4. **Recovery:** System restoration procedures
5. **Lessons Learned:** Security improvement process

### Emergency Procedures

1. **System Compromise:** Immediate shutdown procedures
2. **Data Breach:** Incident response plan
3. **Legal Issues:** Legal counsel contact information
4. **Communication:** Stakeholder notification procedures

## Monitoring and Maintenance

### Regular Tasks

1. **Log Review:** Daily security log review
2. **Dependency Updates:** Monthly security updates
3. **Configuration Review:** Quarterly security assessment
4. **Penetration Testing:** Annual security testing
5. **Training:** Regular security awareness training

### Metrics to Monitor

1. **Failed Login Attempts:** Authentication security
2. **Rate Limit Triggers:** Potential attacks
3. **Validation Failures:** Input security
4. **Template Rejections:** XSS attempt detection
5. **File Upload Blocks:** DoS attempt detection

## Support and Updates

For security issues or questions:
1. Review this documentation
2. Check the test suite for examples
3. Review the code for implementation details
4. Contact the development team for critical issues

**Remember:** Security is an ongoing process, not a one-time implementation. Regular review and updates are essential for maintaining a secure system.