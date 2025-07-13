from flask import Blueprint

# Crearea Blueprint-ului pentru fake revolut
bp = Blueprint('fake_revolut', __name__, url_prefix='/revolut')

@bp.route('/')
def index():
    """Fake Revolut site"""
    return "Fake Revolut - Under Construction"
