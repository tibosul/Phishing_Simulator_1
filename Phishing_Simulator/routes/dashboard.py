from flask import Blueprint, render_template

# Crearea Blueprint-ului pentru dashboard
bp = Blueprint('dashboard', __name__, url_prefix='/admin')

@bp.route('/')
def index():
    """Dashboard principal"""
    return "Dashboard - Under Construction"
