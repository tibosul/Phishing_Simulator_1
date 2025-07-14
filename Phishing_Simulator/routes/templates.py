# ==========================================
# routes/templates.py - STUB
# ==========================================

"""
Templates routes - Gestionarea template-urilor
TODO: Implementare completă
"""

from flask import Blueprint

bp = Blueprint('templates', __name__)

@bp.route('/')
def list_templates():
    """Lista template-urilor - STUB"""
    return "<h1>📧 Templates Management</h1><p>Coming soon...</p>"

@bp.route('/create')
def create_template():
    """Crearea template-urilor - STUB"""
    return "<h1>➕ Create Template</h1><p>Coming soon...</p>"