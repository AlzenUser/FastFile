from functools import wraps
from flask import session, redirect, url_for, request, jsonify, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from api import models


def hash_password(password):
    """Hash a password using pbkdf2."""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password_hash, password):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def login_required(f):
    """Decorator: redirects to login if user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Load user into g for easy access
        user = models.get_user_by_id(current_app.config['DATABASE'], session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated


def require_auth(f):
    """
    Decorator: protects API routes using the Bearer token stored in the session.
    The token is NEVER sent from the client JS — it is retrieved server-side
    from the session, then validated against the database.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from server-side session (not from client headers)
        api_token = session.get('api_token')
        if not api_token:
            return jsonify({'error': 'Non authentifié'}), 401

        user = models.get_user_by_token(current_app.config['DATABASE'], api_token)
        if not user:
            session.clear()
            return jsonify({'error': 'Token invalide'}), 401

        g.user = user
        return f(*args, **kwargs)
    return decorated
