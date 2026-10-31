
from flask import Blueprint, request, jsonify
from . import llm

# Create Flask Blueprint
router = Blueprint("genai", __name__, url_prefix="/genai")


# 1. Generate customer reply
@router.route("/suggest-reply", methods=["POST"])
def suggest_reply():
    data = request.get_json(silent=True) or {}

    ticket_text = data.get("ticket_text")

    if not ticket_text:
        return jsonify({"error": "ticket_text is required"}), 400

    customer = data.get("customer", {
        "name": "Customer",
        "plan": None
    })

    kb_articles = data.get("kb_articles", [])

    sentiment = data.get("sentiment", {
        "sentiment": "neutral"
    })

    tone = data.get("tone", "professional")

    result = llm.suggest_reply(
        ticket_text,
        customer,
        kb_articles,
        sentiment,
        tone
    )

    return jsonify(result)


# 2. Summarize ticket conversation
@router.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json(silent=True) or {}

    history = data.get("history", [])

    result = llm.summarize_ticket(history)

    return jsonify(result)


# 3. Generate weekly CSAT report
@router.route("/csat-report", methods=["POST"])
def csat():
    stats = request.get_json(silent=True) or {}

    result = llm.weekly_csat_report(stats)

    return jsonify(result)
