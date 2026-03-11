from flask import Flask, session
from datetime import timedelta
from flask_socketio import SocketIO


socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

def create_app():
    app = Flask(__name__)

    @app.context_processor
    def inject_display_name():
        """Anzeigename (Teil vor @) aus User-E-Mail für Navbar/Header bereitstellen."""
        email = session.get("user_email") if session else None
        if email and "@" in str(email):
            display_name = str(email).split("@")[0]
        else:
            display_name = None
        return dict(display_name=display_name)

    app.config["SECRET_KEY"] = "dev"
    # Session: 8 Stunden aktiv (kein vorzeitiges Ausloggen bei normaler Nutzung)
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    from .routes import bp as main_bp, limiter, register_socket_events
    app.register_blueprint(main_bp)
    limiter.init_app(app)
    socketio.init_app(app)
    register_socket_events(socketio)

    return app
