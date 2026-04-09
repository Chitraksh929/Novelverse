import hashlib, os, hmac, time
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g

def hash_password(password):
    salt = os.urandom(32).hex()
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return pw_hash, salt

def verify_password(password, stored_hash, salt):
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()
    return pw_hash == stored_hash

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def author_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        if not session.get('is_author'):
            flash('Author account required.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ── CSRF Protection ────────────────────────────────────────────────────────────

def generate_csrf_token():
    """Generate a per-session CSRF token. Stored in session, regenerated if absent."""
    if 'csrf_token' not in session:
        session['csrf_token'] = hmac.new(
            key=os.urandom(32),
            msg=os.urandom(32),
            digestmod=hashlib.sha256
        ).hexdigest()
    return session['csrf_token']

def validate_csrf_token():
    """
    Validate the CSRF token for state-changing requests.
    Accepts token from form field OR X-CSRF-Token header (for AJAX).
    Returns True if valid, False otherwise.
    """
    token_in_session = session.get('csrf_token')
    if not token_in_session:
        return False
    # Check form field first, then header (for JSON API calls)
    token_submitted = (
        request.form.get('csrf_token') or
        request.headers.get('X-CSRF-Token') or
        (request.get_json(silent=True) or {}).get('csrf_token')
    )
    if not token_submitted:
        return False
    # Use hmac.compare_digest to prevent timing attacks
    return hmac.compare_digest(token_in_session, token_submitted)

def csrf_protect(f):
    """
    Decorator: validates CSRF token on all POST/PUT/PATCH/DELETE requests.
    Aborts with 403 if token is missing or invalid.
    Usage: @csrf_protect on any route that mutates state.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if not validate_csrf_token():
                # JSON API — return JSON error
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from flask import jsonify
                    return jsonify({'error': 'CSRF token missing or invalid.'}), 403
                # HTML form — flash and redirect back
                flash('Security token expired or invalid. Please try again.', 'error')
                return redirect(request.referrer or url_for('home'))
        return f(*args, **kwargs)
    return decorated
