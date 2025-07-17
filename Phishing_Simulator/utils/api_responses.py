#!/usr/bin/env python3
"""
Standardized API response utilities for consistent error handling
"""

from flask import jsonify
import logging

def success_response(data=None, message="Success", status_code=200):
    """
    Returnează un răspuns de succes standardizat
    
    Args:
        data: Datele de returnat
        message: Mesajul de succes
        status_code: Codul de stare HTTP
        
    Returns:
        tuple: (response, status_code)
    """
    response = {
        'success': True,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code


def error_response(message="An error occurred", status_code=500, error_type=None, details=None):
    """
    Returnează un răspuns de eroare standardizat
    
    Args:
        message: Mesajul de eroare
        status_code: Codul de stare HTTP
        error_type: Tipul erorii (validation, authentication, etc.)
        details: Detalii suplimentare despre eroare
        
    Returns:
        tuple: (response, status_code)
    """
    response = {
        'success': False,
        'error': message
    }
    
    if error_type:
        response['error_type'] = error_type
    
    if details:
        response['details'] = details
    
    # Log error pentru monitoring
    if status_code >= 500:
        logging.error(f"API Error {status_code}: {message} | Details: {details}")
    elif status_code >= 400:
        logging.warning(f"API Client Error {status_code}: {message}")
    
    return jsonify(response), status_code


def validation_error_response(message="Validation failed", details=None):
    """
    Returnează un răspuns pentru erori de validare
    
    Args:
        message: Mesajul de eroare
        details: Lista cu erorile specifice de validare
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=message,
        status_code=400,
        error_type="validation_error",
        details=details
    )


def not_found_response(resource="Resource"):
    """
    Returnează un răspuns pentru resurse negăsite
    
    Args:
        resource: Numele resursei negăsite
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=f"{resource} not found",
        status_code=404,
        error_type="not_found"
    )


def unauthorized_response(message="Unauthorized access"):
    """
    Returnează un răspuns pentru acces neautorizat
    
    Args:
        message: Mesajul de eroare
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=message,
        status_code=401,
        error_type="unauthorized"
    )


def forbidden_response(message="Access forbidden"):
    """
    Returnează un răspuns pentru acces interzis
    
    Args:
        message: Mesajul de eroare
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=message,
        status_code=403,
        error_type="forbidden"
    )


def rate_limit_response(message="Rate limit exceeded"):
    """
    Returnează un răspuns pentru rate limiting
    
    Args:
        message: Mesajul de eroare
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=message,
        status_code=429,
        error_type="rate_limit"
    )


def server_error_response(message="Internal server error"):
    """
    Returnează un răspuns pentru erori de server
    
    Args:
        message: Mesajul de eroare
        
    Returns:
        tuple: (response, status_code)
    """
    return error_response(
        message=message,
        status_code=500,
        error_type="server_error"
    )


def csv_import_response(stats, campaign_name=None):
    """
    Returnează un răspuns standardizat pentru import CSV
    
    Args:
        stats: Statisticile importului
        campaign_name: Numele campaniei (opțional)
        
    Returns:
        tuple: (response, status_code)
    """
    if stats['added'] == 0 and stats['errors']:
        return error_response(
            message="CSV import failed - no valid records found",
            status_code=400,
            error_type="import_failed",
            details={
                'stats': stats,
                'campaign': campaign_name
            }
        )
    
    message = f"CSV import completed: {stats['added']} added"
    if stats['skipped'] > 0:
        message += f", {stats['skipped']} skipped"
    if stats['errors']:
        message += f", {len(stats['errors'])} errors"
    
    return success_response(
        data={
            'stats': stats,
            'campaign': campaign_name
        },
        message=message,
        status_code=200 if not stats['errors'] else 207  # 207 = Multi-Status
    )