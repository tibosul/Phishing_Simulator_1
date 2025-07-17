#!/usr/bin/env python3
"""
Simple test to verify the basic security features are working
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.validators import validate_email, validate_phone_number, validate_csv_format, ValidationError
from utils.security import sanitize_input, sanitize_template_content, validate_template_variables

def test_email_validation():
    """Test email validation"""
    print("Testing email validation...")
    
    # Valid emails
    try:
        validate_email("user@example.com")
        print("✓ Valid email accepted")
    except ValidationError:
        print("✗ Valid email rejected")
        return False
    
    # Invalid email
    try:
        validate_email("invalid.email")
        print("✗ Invalid email accepted")
        return False
    except ValidationError:
        print("✓ Invalid email rejected")
    
    return True

def test_phone_validation():
    """Test phone validation"""
    print("Testing phone validation...")
    
    # Valid phone
    try:
        validate_phone_number("+40723456789")
        print("✓ Valid phone accepted")
    except ValidationError:
        print("✗ Valid phone rejected")
        return False
    
    # Invalid phone
    try:
        validate_phone_number("invalid")
        print("✗ Invalid phone accepted")
        return False
    except ValidationError:
        print("✓ Invalid phone rejected")
    
    return True

def test_csv_limits():
    """Test CSV security limits"""
    print("Testing CSV limits...")
    
    # Valid CSV
    try:
        validate_csv_format("email,name\nuser@example.com,User")
        print("✓ Valid CSV accepted")
    except ValidationError:
        print("✗ Valid CSV rejected")
        return False
    
    # Too large CSV
    try:
        large_csv = "email,name\n" + ("user@example.com,User\n" * 15000)
        validate_csv_format(large_csv, max_rows=10000)
        print("✗ Large CSV accepted")
        return False
    except ValidationError:
        print("✓ Large CSV rejected")
    
    return True

def test_template_sanitization():
    """Test template sanitization"""
    print("Testing template sanitization...")
    
    # Malicious content
    try:
        sanitize_template_content('<script>alert("xss")</script>', 'email')
        print("✗ Malicious template accepted")
        return False
    except ValidationError:
        print("✓ Malicious template rejected")
    
    # Valid content
    try:
        result = sanitize_template_content('<p>Hello {{first_name}}</p>', 'email')
        print("✓ Valid template sanitized")
    except ValidationError:
        print("✗ Valid template rejected")
        return False
    
    return True

def test_template_variables():
    """Test template variable validation"""
    print("Testing template variables...")
    
    # Valid variables
    try:
        validate_template_variables("Hello {{first_name}}, visit {{tracking_link}}")
        print("✓ Valid template variables accepted")
    except ValidationError:
        print("✗ Valid template variables rejected")
        return False
    
    # Invalid variables
    try:
        validate_template_variables("Hello {{eval('evil')}}")
        print("✗ Invalid template variables accepted")
        return False
    except ValidationError:
        print("✓ Invalid template variables rejected")
    
    return True

def main():
    """Run all security tests"""
    print("Running basic security validation tests...\n")
    
    tests = [
        test_email_validation,
        test_phone_validation,
        test_csv_limits,
        test_template_sanitization,
        test_template_variables
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All security tests passed!")
        return True
    else:
        print("❌ Some security tests failed!")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)