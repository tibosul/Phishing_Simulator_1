from flask import Blueprint

# Crearea Blueprint-ului pentru targets
bp = Blueprint('targets', __name__, url_prefix='/admin/targets')

@bp.route('/')
def list_targets():
    """Lista targets"""
    return "Targets - Under Construction"
