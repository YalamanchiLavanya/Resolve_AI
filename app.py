import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import Flask, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from werkzeug.exceptions import HTTPException

from config import Config
from database import db_session, get_db_connection
from routes.ai import ai_bp
from routes.auth import auth_bp
from routes.customers import customers_bp
from routes.dashboard import dashboard_bp
from routes.kb import kb_bp
from routes.tickets import tickets_bp
from utils.security import ApiError


class AppJSONProvider(DefaultJSONProvider):
    """MySQL returns Decimal and datetime values; make them JSON friendly."""

    sort_keys = False

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


app = Flask(__name__)
app.config.from_object(Config)
app.json = AppJSONProvider(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

CORS(
    app,
    resources={r"/api/*": {"origins": Config.FRONTEND_ORIGINS}},
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)

jwt = JWTManager(app)


@jwt.unauthorized_loader
def _missing_token(reason):
    return jsonify({"error": "Authentication required"}), 401


@jwt.invalid_token_loader
def _invalid_token(reason):
    return jsonify({"error": "Invalid token"}), 401


@jwt.expired_token_loader
def _expired_token(header, payload):
    return jsonify({"error": "Session expired. Please log in again"}), 401


@app.errorhandler(ApiError)
def _api_error(e):
    return jsonify({"error": e.message}), e.status


@app.errorhandler(HTTPException)
def _http_error(e):
    return jsonify({"error": e.description}), e.code


@app.errorhandler(Exception)
def _unexpected(e):
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500


app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(customers_bp, url_prefix="/api/customers")
app.register_blueprint(tickets_bp, url_prefix="/api/tickets")
app.register_blueprint(kb_bp, url_prefix="/api/kb")
app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
app.register_blueprint(ai_bp, url_prefix="/api/ai")


@app.route("/")
def home():
    return jsonify({"message": "Welcome to ResolveAI Flask API", "status": "Running"})


@app.route("/api/health")
def health():
    return jsonify({"status": "success", "message": "ResolveAI API is running"})


@app.route("/api/test-db", methods=["GET"])
def test_db():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS database_name")
            result: Any = cursor.fetchone()
        return jsonify({"status": "success", "database": result["database_name"]}), 200
    except Exception:
        app.logger.exception("MySQL connection test failed")
        return jsonify({"status": "error", "message": "Could not connect to MySQL"}), 500
    finally:
        if conn:
            conn.close()


def _start_scheduler():
    """Optional: run SLA / outage jobs from Flask if MySQL events are off."""
    from apscheduler.schedulers.background import BackgroundScheduler

    def run(proc, *args):
        def job():
            try:
                with db_session() as cur:
                    cur.execute(f"CALL {proc}({', '.join(['%s'] * len(args))})", args or None)
            except Exception:
                logging.exception("Scheduled job %s failed", proc)
        return job

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(run("sp_check_sla_breaches"), "interval", minutes=5)
    sched.add_job(run("sp_detect_outages", 5), "interval", minutes=10)
    sched.start()


if Config.ENABLE_SCHEDULER and os.environ.get("WERKZEUG_RUN_MAIN") in (None, "true"):
    _start_scheduler()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
