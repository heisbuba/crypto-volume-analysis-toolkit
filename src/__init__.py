import os
from datetime import timedelta
from flask import Flask

# Import our configuration logic
from .config import init_firebase, FIREBASE_WEB_API_KEY

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24).hex())

    # Cookie settings
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'None'
    app.config['SESSION_COOKIE_SECURE'] = True

    # Initialize Database
    try:
        init_firebase()
    except Exception as e:
        print(f"❌ FATAL: {e}")
    
    # Register Blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.main import main_bp
    from .blueprints.tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(tasks_bp)

    return app