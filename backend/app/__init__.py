from flask import Flask, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentication required. Please log in."}), 401

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    from pathlib import Path
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    (Path(__file__).resolve().parent.parent / "instance").mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.lost_routes import lost_bp
    from app.routes.found_routes import found_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(lost_bp, url_prefix="/api/reports/lost")
    app.register_blueprint(found_bp, url_prefix="/api/reports/found")

    @app.get("/")
    def home():
        return send_from_directory(app.static_folder + "/frontend", "index.html")

    @app.get("/<path:page>")
    def frontend_page(page):
        if page.endswith((".html", ".css", ".js")) or page.startswith(("assets/", "js/")):
            return send_from_directory(app.static_folder + "/frontend", page)
        return jsonify({"error": "Not found"}), 404

    from app.routes.portal import portal_bp
    app.register_blueprint(portal_bp, url_prefix="/api")

    from app import models
    with app.app_context():
        db.create_all()
    return app
