from flask import Blueprint

# Crearea Blueprint-ului pentru webhook
bp = Blueprint('webhook', __name__, url_prefix='/webhook')

@bp.route('/ping')
def ping():
    """Health check pentru webhook"""
    return "Webhook - Under Construction"
