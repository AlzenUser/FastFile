import os
from flask import Flask
from api.config import Config
from api import models
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

def create_app():
    # Flask needs to know where templates and static files are relative to this file
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../templates/static')
    app.config.from_object(Config)

    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=app.config.get("RATELIMIT_STORAGE_URI", "memory://")
    )
    csrf = CSRFProtect(app)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # Initialize database
    models.init_db(app.config['DATABASE'])

    # Register routes and filters
    from api.routes import register_routes
    register_routes(app, limiter)

    return app
