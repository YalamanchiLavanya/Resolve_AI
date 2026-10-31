"""Flask Blueprint for ResolveAI AI/ML endpoints."""
from flask import Blueprint, request, jsonify
from . import ml_models, sentiment, outage

router = Blueprint("aiml", __name__, url_prefix="/ml")


def get_json():
    return request.get_json(silent=True) or {}


@router.route("/analyze-ticket", methods=["POST"])
def analyze_ticket():
    data = get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    customer = data.get("customer") or {}
    s = sentiment.analyze(
        text,
        int(customer.get("previous_tickets_30d", 0)),
        int(customer.get("escalations", 0)),
    )
    result = ml_models.classify(text, s["at_risk"], customer.get("plan"))
    result["sentiment"] = s
    result["similar"] = ml_models.kb_index.query(text)
    return jsonify(result)


@router.route("/sentiment", methods=["POST"])
def sentiment_api():
    data = get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    customer = data.get("customer") or {}
    result = sentiment.analyze(
        text,
        int(customer.get("previous_tickets_30d", 0)),
        int(customer.get("escalations", 0)),
    )
    return jsonify(result)


@router.route("/similar", methods=["POST"])
def similar():
    data = get_json()
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    return jsonify({"similar": ml_models.kb_index.query(text)})


@router.route("/outages/detect", methods=["POST"])
def outages():
    data = get_json()
    tickets = data.get("tickets", [])
    if not isinstance(tickets, list):
        return jsonify({"error": "tickets must be a list"}), 400
    try:
        alerts = outage.detect(
            tickets,
            int(data.get("window_minutes", 60)),
            int(data.get("threshold", 5)),
            data.get("now"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid ticket data: {exc}"}), 400
    return jsonify({"alerts": alerts})


@router.route("/kb/reindex", methods=["POST"])
def reindex():
    data = get_json()
    docs = data.get("docs", [])
    if not isinstance(docs, list):
        return jsonify({"error": "docs must be a list"}), 400
    try:
        ml_models.kb_index.build(docs)
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid knowledge-base documents: {exc}"}), 400
    return jsonify({"indexed": len(docs)})
