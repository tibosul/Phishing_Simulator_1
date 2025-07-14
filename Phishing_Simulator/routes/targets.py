# ==========================================
# routes/targets.py - STUB
# ==========================================

"""
Targets routes - Gestionarea țintelor
TODO: Implementare completă
"""

from flask import Blueprint

bp = Blueprint('targets', __name__)

@bp.route('/')
def list_targets():
    """Lista țintelor - STUB"""
    return "<h1>📧 Targets Management</h1><p>Coming soon...</p>"

@bp.route('/create')
def create_target():
    """Crearea țintelor - STUB"""
    return "<h1>➕ Create Target</h1><p>Coming soon...</p>"