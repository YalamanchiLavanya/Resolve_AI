from flask import Blueprint, jsonify, request

from config import Config
from database import db_session
from utils import groq_ai
from utils.ai_pipeline import analyze_text
from utils.helpers import find_kb, load_ticket
from utils.security import STAFF_ROLES, ApiError, current_user, role_required

ai_bp = Blueprint("ai", __name__)


def _thread(cur, ticket_id, include_internal):
    sql = """SELECT cm.body, cm.is_internal, u.full_name AS who
               FROM ticket_comments cm JOIN users u ON u.user_id = cm.author_id
              WHERE cm.ticket_id = %s"""
    if not include_internal:
        sql += " AND cm.is_internal = FALSE"
    cur.execute(sql + " ORDER BY cm.created_at", (ticket_id,))
    return cur.fetchall()


@ai_bp.route("/analyze", methods=["POST"])
@role_required()
def analyze():
    """Preview AI triage + KB suggestions while the customer is typing."""
    description = (request.get_json(silent=True) or {}).get("description")
    if not isinstance(description, str) or not description.strip():
        raise ApiError("Description is required")
    with db_session() as cur:
        cur.execute("SELECT category_id, category_name FROM categories")
        cats = cur.fetchall()
        names = [c["category_name"] for c in cats]
        result = analyze_text(description, names)
        cat_id = next((c["category_id"] for c in cats if c["category_name"] == result["category"]), None)
        kb = find_kb(cur, description, cat_id)
    return jsonify({
        "status": "success",
        "analysis": result,
        "suggested_solutions": [
            {"article_id": a["article_id"], "title": a["title"], "solution": a["solution"]}
            for a in kb
        ],
    }), 200


@ai_bp.route("/tickets/<int:ticket_id>/draft-reply", methods=["POST"])
@role_required(*STAFF_ROLES)
def draft_reply(ticket_id):
    """GenAI: draft a customer reply. The agent reviews and sends it."""
    uid, role = current_user()
    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role)
        cur.execute(
            """SELECT u.full_name, p.plan_name, cp.connection_type
                 FROM users u
                 LEFT JOIN customer_profiles cp ON cp.customer_id = u.user_id
                 LEFT JOIN plans p ON p.plan_id = cp.plan_id
                WHERE u.user_id = %s""",
            (t["customer_id"],),
        )
        customer = cur.fetchone() or {}
        kb = find_kb(cur, f"{t['subject']} {t['description']}", t["category_id"])
        thread = _thread(cur, ticket_id, include_internal=False)

        try:
            reply = groq_ai.draft_reply(t, customer, thread, kb)
        except Exception:
            raise ApiError("AI reply drafting is unavailable right now. Try again shortly.", 503)

        cur.execute(
            """INSERT INTO ai_suggestions
                 (ticket_id, suggestion_type, suggested_value, kb_article_id, model_used)
               VALUES (%s, 'REPLY', %s, %s, %s)""",
            (ticket_id, reply, kb[0]["article_id"] if kb else None, Config.GROQ_MODEL),
        )
        suggestion_id = cur.lastrowid
    return jsonify({"suggestion_id": suggestion_id, "reply": reply}), 200


@ai_bp.route("/tickets/<int:ticket_id>/summarize", methods=["POST"])
@role_required(*STAFF_ROLES)
def summarize(ticket_id):
    """GenAI: short hand-over summary of the ticket thread."""
    uid, role = current_user()
    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role)
        thread = _thread(cur, ticket_id, include_internal=True)
    try:
        summary = groq_ai.summarize_ticket(t, thread)
    except Exception:
        raise ApiError("AI summary is unavailable right now. Try again shortly.", 503)
    return jsonify({"summary": summary}), 200


@ai_bp.route("/suggestions/<int:suggestion_id>", methods=["PATCH"])
@role_required(*STAFF_ROLES)
def review_suggestion(suggestion_id):
    """Agent marks an AI suggestion accepted / rejected (feedback loop)."""
    uid, role = current_user()
    accepted = (request.get_json(silent=True) or {}).get("accepted")
    if not isinstance(accepted, bool):
        raise ApiError("accepted (true/false) is required")
    with db_session() as cur:
        cur.execute("SELECT ticket_id FROM ai_suggestions WHERE suggestion_id = %s", (suggestion_id,))
        row = cur.fetchone()
        if not row:
            raise ApiError("Suggestion not found", 404)
        load_ticket(cur, row["ticket_id"], uid, role)
        cur.execute("UPDATE ai_suggestions SET was_accepted = %s WHERE suggestion_id = %s",
                    (accepted, suggestion_id))
    return jsonify({"message": "Feedback saved"}), 200
