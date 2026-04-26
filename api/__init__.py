import os
from flask import Flask
from api.config import Config
from api import models

def create_app():
    # Flask needs to know where templates and static files are relative to this file
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../templates/static')
    app.config.from_object(Config)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # Initialize database
    models.init_db(app.config['DATABASE'])

    # Register routes and filters
    from api.routes import register_routes
    register_routes(app)

    return app
