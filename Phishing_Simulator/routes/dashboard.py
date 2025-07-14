# ==========================================
# routes/dashboard.py - STUB
# ==========================================

"""
Dashboard routes - Pagina principală admin
TODO: Implementare completă
"""

from flask import Blueprint, render_template

bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    """Dashboard principal - STUB"""
    return """
    <h1>🎯 Phishing Simulator Dashboard</h1>
    <p>Dashboard coming soon...</p>
    <ul>
        <li><a href="/admin/campaigns/">Campaigns</a></li>
        <li><a href="/health">Health Check</a></li>
        <li><a href="/api/stats">API Stats</a></li>
    </ul>
    """