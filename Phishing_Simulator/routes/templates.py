from flask import Blueprint

# Crearea Blueprint-ului pentru templates
bp = Blueprint('templates', __name__, url_prefix='/admin/templates')

@bp.route('/')
def list_templates():
    """Lista templates"""
    return "Templates - Under Construction"
