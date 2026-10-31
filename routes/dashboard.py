from flask import Blueprint, jsonify, request

from database import db_session
from utils.helpers import audit
from utils.security import ApiError, current_user, role_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/stats", methods=["GET"])
@role_required("ADMIN", "TEAM_LEAD")
def dashboard_stats():
    with db_session() as cur:
        cur.execute("""
            SELECT COUNT(*) AS total,
                   SUM(status = 'OPEN') AS open_tickets,
                   SUM(status IN ('ASSIGNED','IN_PROGRESS')) AS in_progress,
                   SUM(status = 'PENDING_CUSTOMER') AS pending_customer,
                   SUM(status IN ('RESOLVED','CLOSED')) AS resolved,
                   SUM(is_escalated) AS escalated,
                   SUM(is_at_risk) AS at_risk,
                   SUM(sla_breached) AS sla_breached,
                   SUM(priority = 'CRITICAL' AND status NOT IN ('RESOLVED','CLOSED')) AS critical_open,
                   SUM(status NOT IN ('RESOLVED','CLOSED') AND sla_breached = FALSE
                       AND resolution_due BETWEEN NOW() AND NOW() + INTERVAL 60 MINUTE) AS breaching_within_hour,
                   ROUND(100 * (1 - SUM(sla_breached) / NULLIF(COUNT(*), 0)), 2) AS sla_compliance_pct,
                   ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, first_responded_at)), 1) AS avg_first_response_min,
                   ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, resolved_at)), 1) AS avg_resolution_min,
                   SUM(first_responded_at IS NOT NULL AND first_responded_at <= first_response_due) AS first_response_met,
                   SUM(first_responded_at IS NOT NULL) AS first_response_total
              FROM tickets""")
        stats = cur.fetchone() or {}

        cur.execute("SELECT ROUND(AVG(rating), 2) AS average_rating, COUNT(*) AS responses FROM ticket_ratings")
        csat = cur.fetchone() or {}
        cur.execute("SELECT rating, COUNT(*) AS count FROM ticket_ratings GROUP BY rating ORDER BY rating")
        csat["distribution"] = cur.fetchall()

        cur.execute("SELECT sentiment, COUNT(*) AS count FROM tickets WHERE sentiment IS NOT NULL GROUP BY sentiment")
        sentiment = cur.fetchall()

        cur.execute("""SELECT DATE(created_at) AS day, COUNT(*) AS count FROM tickets
                        WHERE created_at >= CURDATE() - INTERVAL 6 DAY
                        GROUP BY DATE(created_at) ORDER BY day""")
        trend = cur.fetchall()

        cur.execute("SELECT * FROM v_sla_metrics")
        sla_by_priority = cur.fetchall()
        cur.execute("SELECT * FROM v_queue_summary")
        queues = cur.fetchall()
        cur.execute("SELECT * FROM v_agent_performance ORDER BY resolved DESC")
        agents = cur.fetchall()
        cur.execute("SELECT * FROM v_category_stats ORDER BY total_tickets DESC")
        categories = cur.fetchall()
        cur.execute("SELECT * FROM v_active_outages")
        outages = cur.fetchall()
        cur.execute("SELECT * FROM weekly_csat_reports ORDER BY week_start DESC LIMIT 8")
        weekly = cur.fetchall()

    return jsonify({
        "stats": stats,
        "csat": csat,
        "sla_by_priority": sla_by_priority,
        "queues": queues,
        "agent_performance": agents,
        "categories": categories,
        "sentiment": sentiment,
        "tickets_last_7_days": trend,
        "active_outages": outages,
        "weekly_csat": weekly,
        # kept for backward compatibility with the old frontend
        "average_rating": csat.get("average_rating"),
    }), 200


@dashboard_bp.route("/run-sla-check", methods=["POST"])
@role_required("ADMIN", "TEAM_LEAD")
def run_sla_check():
    """Manually run SLA breach detection + escalation."""
    uid, _ = current_user()
    with db_session() as cur:
        cur.execute("CALL sp_check_sla_breaches()")
        audit(cur, uid, "RUN_SLA_CHECK")
    return jsonify({"message": "SLA check completed"}), 200


@dashboard_bp.route("/detect-outages", methods=["POST"])
@role_required("ADMIN", "TEAM_LEAD")
def detect_outages():
    uid, _ = current_user()
    try:
        threshold = int((request.get_json(silent=True) or {}).get("threshold", 5))
    except (TypeError, ValueError):
        raise ApiError("threshold must be a number")
    if not 2 <= threshold <= 100:
        raise ApiError("threshold must be between 2 and 100")
    with db_session() as cur:
        cur.execute("CALL sp_detect_outages(%s)", (threshold,))
        audit(cur, uid, "RUN_OUTAGE_DETECTION", str(threshold))
    return jsonify({"message": "Outage detection completed"}), 200


@dashboard_bp.route("/weekly-csat", methods=["POST"])
@role_required("ADMIN")
def weekly_csat():
    uid, _ = current_user()
    with db_session() as cur:
        cur.execute("CALL sp_generate_weekly_csat(DATE_SUB(CURDATE(), INTERVAL 6 DAY))")
        audit(cur, uid, "GENERATE_WEEKLY_CSAT")
    return jsonify({"message": "Weekly CSAT report generated"}), 200
