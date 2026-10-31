import os
import uuid
from typing import Any

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from database import db_session
from utils.ai_pipeline import analyze_text
from utils.helpers import (audit, find_kb, hist_mark, hist_stamp, load_ticket,
                           notify)
from utils.security import STAFF_ROLES, ApiError, current_user, role_required

tickets_bp = Blueprint("tickets", __name__)

PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
STATUSES = ("OPEN", "ASSIGNED", "IN_PROGRESS", "PENDING_CUSTOMER", "RESOLVED", "CLOSED")
CHANNELS = ("EMAIL", "APP", "PHONE", "WEB")
MAX_FILES = 5

LIST_SQL = """
SELECT t.ticket_id, t.ticket_number, t.subject, t.status, t.priority, t.channel,
       t.sentiment, t.is_at_risk, t.is_escalated, t.escalation_level,
       t.sla_breached, t.first_response_due, t.resolution_due,
       t.created_at, t.updated_at, t.category_id, c.category_name,
       t.assigned_agent_id, ag.full_name AS agent_name,
       t.team_id, tm.team_name,
       t.customer_id, cu.full_name AS customer_name
  FROM tickets t
  JOIN users cu ON cu.user_id = t.customer_id
  LEFT JOIN categories c ON c.category_id = t.category_id
  LEFT JOIN users ag ON ag.user_id = t.assigned_agent_id
  LEFT JOIN teams tm ON tm.team_id = t.team_id"""


# ------------------------------------------------------------------ helpers
def _save_attachments(cur, ticket_id, uploader_id, files):
    files = [f for f in files if f and f.filename]
    if len(files) > MAX_FILES:
        raise ApiError(f"At most {MAX_FILES} attachments per request")
    saved = []
    for f in files:
        original = secure_filename(f.filename)
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
        if ext not in current_app.config["ALLOWED_EXTENSIONS"]:
            raise ApiError(f"File type .{ext or '?'} is not allowed")
        stored = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
        f.save(path)
        size_kb = max(1, os.path.getsize(path) // 1024)
        cur.execute(
            """INSERT INTO ticket_attachments
                  (ticket_id, uploaded_by, file_name, file_path, file_type, file_size_kb)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (ticket_id, uploader_id, original, stored, ext, size_kb),
        )
        saved.append({"attachment_id": cur.lastrowid, "file_name": original})
    return saved


def _team_lead_of(cur, team_id):
    if not team_id:
        return None
    cur.execute("SELECT team_lead_id FROM teams WHERE team_id = %s", (team_id,))
    row = cur.fetchone()
    return row["team_lead_id"] if row else None


def _staff_can_modify(t, uid, role):
    if role == "SUPPORT_AGENT" and t["assigned_agent_id"] != uid:
        raise ApiError("Only the assigned agent can change this ticket", 403)


# ------------------------------------------------------------------ list
@tickets_bp.route("", methods=["GET"], strict_slashes=False)
@role_required()
def list_tickets():
    uid, role = current_user()
    where, params = [], []

    if role == "CUSTOMER":
        where.append("t.customer_id = %s")
        params.append(uid)
    elif role == "SUPPORT_AGENT":
        where.append(
            """(t.assigned_agent_id = %s OR (t.assigned_agent_id IS NULL AND t.team_id IN
               (SELECT team_id FROM team_members WHERE user_id = %s)))"""
        )
        params += [uid, uid]
    elif role == "TEAM_LEAD":
        where.append("tm.team_lead_id = %s")
        params.append(uid)

    status = request.args.get("status")
    if status:
        if status.upper() not in STATUSES:
            raise ApiError("Invalid status filter")
        where.append("t.status = %s")
        params.append(status.upper())
    priority = request.args.get("priority")
    if priority:
        if priority.upper() not in PRIORITIES:
            raise ApiError("Invalid priority filter")
        where.append("t.priority = %s")
        params.append(priority.upper())
    if request.args.get("escalated") == "true":
        where.append("t.is_escalated = TRUE")
    if request.args.get("breached") == "true":
        where.append("t.sla_breached = TRUE")
    q = (request.args.get("q") or "").strip()
    if q:
        where.append("(t.subject LIKE %s OR t.ticket_number LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]

    try:
        page = max(1, int(request.args.get("page", 1)))
        size = min(100, max(1, int(request.args.get("page_size", 50))))
    except ValueError:
        raise ApiError("page and page_size must be numbers")

    sql = LIST_SQL
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY FIELD(t.priority,'CRITICAL','HIGH','MEDIUM','LOW'), "
            "t.created_at DESC LIMIT %s OFFSET %s")
    params += [size, (page - 1) * size]

    with db_session() as cur:
        cur.execute(sql, params)
        return jsonify(cur.fetchall()), 200


# ------------------------------------------------------------------ create
@tickets_bp.route("", methods=["POST"], strict_slashes=False)
@role_required("CUSTOMER", "SUPPORT_AGENT", "TEAM_LEAD", "ADMIN")
def create_ticket():
    uid, role = current_user()

    data: dict[str, Any]
    if (request.content_type or "").startswith("multipart/"):
        data, files = dict(request.form), request.files.getlist("attachments")
    else:
        data, files = request.get_json(silent=True) or {}, []

    subject, description = data.get("subject"), data.get("description")
    if not isinstance(subject, str) or not subject.strip():
        raise ApiError("Subject is required")
    if not isinstance(description, str) or not description.strip():
        raise ApiError("Description is required")
    subject, description = subject.strip(), description.strip()
    if len(subject) > 200:
        raise ApiError("Subject must be 200 characters or fewer")
    if len(description) > 5000:
        raise ApiError("Description must be 5000 characters or fewer")

    if role == "CUSTOMER":
        customer_id = uid
    else:
        try:
            customer_id = int(data.get("customer_id") or 0)
            if customer_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ApiError("customer_id is required when raising a ticket for a customer")

    channel = str(data.get("channel") or "WEB").upper()
    if channel not in CHANNELS:
        channel = "WEB"
    chosen_priority = str(data.get("priority") or "").upper() or None
    if chosen_priority and chosen_priority not in PRIORITIES:
        raise ApiError("priority must be LOW, MEDIUM, HIGH or CRITICAL")

    with db_session() as cur:
        cur.execute(
            """SELECT u.user_id, cp.pincode FROM users u
                 JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'CUSTOMER'
                 LEFT JOIN customer_profiles cp ON cp.customer_id = u.user_id
                WHERE u.user_id = %s AND u.is_active = TRUE""",
            (customer_id,),
        )
        customer = cur.fetchone()
        if not customer:
            raise ApiError("Customer not found", 404)

        cur.execute("SELECT category_id, category_name, default_team_id FROM categories")
        cats = cur.fetchall()
        by_name = {c["category_name"]: c for c in cats}
        by_id = {c["category_id"]: c for c in cats}

        # ---- AI analysis (GenAI first, ML fallback)
        ai = analyze_text(f"{subject}. {description}", list(by_name))
        ai_cat = by_name.get(ai["category"])

        # ---- category / priority: customer's choice wins, else AI
        category = None
        if data.get("category_id"):
            try:
                category = by_id.get(int(data["category_id"]))
            except ValueError:
                category = None
            if not category:
                raise ApiError("Unknown category_id")
        category = category or ai_cat
        priority = chosen_priority or ai["priority"]

        cur.execute(
            """SELECT COUNT(*) AS c FROM tickets
                WHERE customer_id = %s AND created_at >= NOW() - INTERVAL 7 DAY""",
            (customer_id,),
        )
        repeats = cur.fetchone()["c"]

        outage_id = None
        if customer["pincode"]:
            cur.execute(
                """SELECT outage_id FROM outages
                    WHERE pincode = %s AND status <> 'RESOLVED'
                    ORDER BY detected_at DESC LIMIT 1""",
                (customer["pincode"],),
            )
            row = cur.fetchone()
            outage_id = row["outage_id"] if row else None

        cur.execute(
            """INSERT INTO tickets
                 (customer_id, category_id, subject, description, channel, priority,
                  team_id, ai_category_id, ai_confidence, sentiment, sentiment_score,
                  repeat_contact_count, outage_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                customer_id, category["category_id"] if category else None,
                subject, description, channel, priority,
                category["default_team_id"] if category else None,
                ai_cat["category_id"] if ai_cat else None, ai["confidence"],
                ai["sentiment"], ai["sentiment_score"], repeats, outage_id,
            ),
        )
        ticket_id = cur.lastrowid
        cur.execute(
            "UPDATE tickets SET ticket_number = CONCAT('TKT-', LPAD(ticket_id, 6, '0')) "
            "WHERE ticket_id = %s",
            (ticket_id,),
        )

        # ---- routing: least-loaded agent in the team
        cur.execute("CALL sp_auto_assign(%s)", (ticket_id,))

        # ---- escalation for angry / repeat customers
        reason = ("ANGRY_CUSTOMER" if ai["sentiment"] == "ANGRY"
                  else "REPEAT_CONTACT" if repeats >= 2 else None)
        lead = _team_lead_of(cur, category["default_team_id"] if category else None)
        if reason:
            cur.execute(
                """INSERT INTO ticket_escalations (ticket_id, level, reason, escalated_to, notes)
                   VALUES (%s, 1, %s, %s, 'Auto-escalated at creation')""",
                (ticket_id, reason, lead),
            )
            cur.execute(
                """UPDATE tickets SET is_escalated = TRUE, escalation_level = 1,
                          is_at_risk = TRUE WHERE ticket_id = %s""",
                (ticket_id,),
            )
            notify(cur, lead, ticket_id, f"At-risk customer escalated: TKT-{ticket_id:06d}")

        cur.execute(
            "SELECT ticket_number, assigned_agent_id, status FROM tickets WHERE ticket_id = %s",
            (ticket_id,),
        )
        created = cur.fetchone()
        notify(cur, created["assigned_agent_id"], ticket_id,
               f"New ticket assigned: {created['ticket_number']}")

        # ---- AI audit trail + KB suggestions
        kb = find_kb(cur, f"{subject} {description}",
                     category["category_id"] if category else None)
        sugg = [
            ("CATEGORY", ai["category"], None, ai["confidence"]),
            ("PRIORITY", ai["priority"], None, ai["confidence"]),
            ("SENTIMENT", f"{ai['sentiment']} ({ai['sentiment_score']})", None, ai["confidence"]),
        ]
        if outage_id:
            sugg.append(("OUTAGE", f"Linked to active outage #{outage_id}", None, None))
        sugg += [("KB_MATCH", a["title"], a["article_id"], None) for a in kb]
        for kind, value, kb_id, conf in sugg:
            cur.execute(
                """INSERT INTO ai_suggestions
                     (ticket_id, suggestion_type, suggested_value, kb_article_id,
                      model_used, confidence)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (ticket_id, kind, value, kb_id,
                 "tfidf-fulltext" if kind == "KB_MATCH" else ai["model_name"], conf),
            )

        attachments = _save_attachments(cur, ticket_id, uid, files)
        audit(cur, uid, "CREATE_TICKET", created["ticket_number"])

    return jsonify({
        "message": "Ticket created successfully",
        "ticket_id": ticket_id,
        "ticket_number": created["ticket_number"],
        "status": created["status"],
        "ai_analysis": ai,
        "linked_outage_id": outage_id,
        "suggested_solutions": [
            {"article_id": a["article_id"], "title": a["title"], "solution": a["solution"]}
            for a in kb
        ],
        "attachments": attachments,
    }), 201


# ------------------------------------------------------------------ detail
@tickets_bp.route("/<int:ticket_id>", methods=["GET"])
@role_required()
def get_ticket(ticket_id):
    uid, role = current_user()
    is_staff = role in STAFF_ROLES
    with db_session() as cur:
        load_ticket(cur, ticket_id, uid, role)
        cur.execute(LIST_SQL + " WHERE t.ticket_id = %s", (ticket_id,))
        ticket = cur.fetchone()
        cur.execute("SELECT description, first_responded_at, resolved_at, closed_at, "
                    "ai_confidence, sentiment_score, repeat_contact_count, outage_id "
                    "FROM tickets WHERE ticket_id = %s", (ticket_id,))
        ticket.update(cur.fetchone())

        cur.execute(
            """SELECT cm.comment_id, cm.body, cm.is_internal, cm.is_ai_generated,
                      cm.created_at, u.full_name AS author, r.role_name AS author_role
                 FROM ticket_comments cm
                 JOIN users u ON u.user_id = cm.author_id
                 JOIN roles r ON r.role_id = u.role_id
                WHERE cm.ticket_id = %s """ + ("" if is_staff else "AND cm.is_internal = FALSE ")
            + "ORDER BY cm.created_at",
            (ticket_id,),
        )
        ticket["comments"] = cur.fetchall()

        cur.execute(
            """SELECT h.field_name, h.old_value, h.new_value, h.changed_at,
                      u.full_name AS changed_by
                 FROM ticket_history h LEFT JOIN users u ON u.user_id = h.changed_by
                WHERE h.ticket_id = %s """ + ("" if is_staff else "AND h.field_name = 'STATUS' ")
            + "ORDER BY h.history_id",
            (ticket_id,),
        )
        ticket["history"] = cur.fetchall()

        cur.execute(
            """SELECT attachment_id, file_name, file_type, file_size_kb, uploaded_at
                 FROM ticket_attachments WHERE ticket_id = %s""",
            (ticket_id,),
        )
        ticket["attachments"] = cur.fetchall()

        cur.execute("SELECT rating, feedback, rated_at FROM ticket_ratings WHERE ticket_id = %s",
                    (ticket_id,))
        ticket["rating"] = cur.fetchone()

        if is_staff:
            cur.execute(
                """SELECT suggestion_id, suggestion_type, suggested_value, kb_article_id,
                          model_used, confidence, was_accepted, created_at
                     FROM ai_suggestions WHERE ticket_id = %s ORDER BY suggestion_id""",
                (ticket_id,),
            )
            ticket["ai_suggestions"] = cur.fetchall()
            cur.execute(
                """SELECT level, reason, notes, escalated_at FROM ticket_escalations
                    WHERE ticket_id = %s ORDER BY escalation_id""",
                (ticket_id,),
            )
            ticket["escalations"] = cur.fetchall()
    return jsonify(ticket), 200


# ------------------------------------------------------------------ status
@tickets_bp.route("/<int:ticket_id>/status", methods=["PATCH"])
@role_required()
def update_status(ticket_id):
    uid, role = current_user()
    status = str((request.get_json(silent=True) or {}).get("status", "")).upper()
    if status not in STATUSES:
        raise ApiError(f"status must be one of {', '.join(STATUSES)}")

    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role, write=True)

        if role == "CUSTOMER":
            if not (status == "CLOSED" and t["status"] == "RESOLVED"):
                raise ApiError("Customers can only close a resolved ticket", 403)
        else:
            _staff_can_modify(t, uid, role)

        mark = hist_mark(cur, ticket_id)
        if status == "CLOSED":
            cur.execute(
                """UPDATE tickets SET status = %s, resolved_at = COALESCE(resolved_at, NOW())
                    WHERE ticket_id = %s""",
                (status, ticket_id),
            )
        else:
            cur.execute("UPDATE tickets SET status = %s WHERE ticket_id = %s",
                        (status, ticket_id))
        hist_stamp(cur, ticket_id, mark, uid)

        if status in ("RESOLVED", "CLOSED") and role != "CUSTOMER":
            notify(cur, t["customer_id"], ticket_id,
                   f"Your ticket {t['ticket_number']} is {status.lower()}. Please rate our service.")
        audit(cur, uid, "UPDATE_STATUS", f"{t['ticket_number']} -> {status}")
    return jsonify({"message": "Ticket updated successfully",
                    "ticket_id": ticket_id, "status": status}), 200


# ------------------------------------------------------------------ priority
@tickets_bp.route("/<int:ticket_id>/priority", methods=["PATCH"])
@role_required(*STAFF_ROLES)
def update_priority(ticket_id):
    uid, role = current_user()
    priority = str((request.get_json(silent=True) or {}).get("priority", "")).upper()
    if priority not in PRIORITIES:
        raise ApiError("priority must be LOW, MEDIUM, HIGH or CRITICAL")
    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role, write=True)
        _staff_can_modify(t, uid, role)
        mark = hist_mark(cur, ticket_id)
        cur.execute("UPDATE tickets SET priority = %s WHERE ticket_id = %s",
                    (priority, ticket_id))  # trigger recalculates SLA dates
        hist_stamp(cur, ticket_id, mark, uid)
    return jsonify({"message": "Priority updated (SLA recalculated)",
                    "priority": priority}), 200


# ------------------------------------------------------------------ assign
@tickets_bp.route("/<int:ticket_id>/assign", methods=["PATCH"])
@role_required("TEAM_LEAD", "ADMIN")
def assign_ticket(ticket_id):
    uid, role = current_user()
    data = request.get_json(silent=True) or {}
    try:
        agent_id = int(data.get("agent_id") or 0)
        if agent_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise ApiError("agent_id is required")

    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role, write=True)
        cur.execute(
            """SELECT u.user_id FROM users u
                 JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'SUPPORT_AGENT'
                WHERE u.user_id = %s AND u.is_active = TRUE""",
            (agent_id,),
        )
        if not cur.fetchone():
            raise ApiError("Active support agent not found", 404)

        if role == "TEAM_LEAD" and t["team_id"]:
            cur.execute("SELECT 1 AS x FROM team_members WHERE team_id = %s AND user_id = %s",
                        (t["team_id"], agent_id))
            if not cur.fetchone():
                raise ApiError("Agent is not a member of this ticket's team")

        mark = hist_mark(cur, ticket_id)
        cur.execute("UPDATE tickets SET assigned_agent_id = %s WHERE ticket_id = %s",
                    (agent_id, ticket_id))  # trigger: OPEN -> ASSIGNED
        hist_stamp(cur, ticket_id, mark, uid)
        notify(cur, agent_id, ticket_id, f"Ticket assigned to you: {t['ticket_number']}")
        audit(cur, uid, "ASSIGN_TICKET", f"{t['ticket_number']} -> user {agent_id}")
    return jsonify({"message": "Ticket assigned", "agent_id": agent_id}), 200


@tickets_bp.route("/<int:ticket_id>/auto-assign", methods=["POST"])
@role_required("TEAM_LEAD", "ADMIN")
def auto_assign(ticket_id):
    uid, role = current_user()
    with db_session() as cur:
        load_ticket(cur, ticket_id, uid, role, write=True)
        mark = hist_mark(cur, ticket_id)
        cur.execute("CALL sp_auto_assign(%s)", (ticket_id,))
        hist_stamp(cur, ticket_id, mark, uid)
        cur.execute("SELECT assigned_agent_id FROM tickets WHERE ticket_id = %s", (ticket_id,))
        agent = cur.fetchone()["assigned_agent_id"]
    return jsonify({"message": "Auto-assign complete", "agent_id": agent}), 200


# ------------------------------------------------------------------ escalate
@tickets_bp.route("/<int:ticket_id>/escalate", methods=["POST"])
@role_required(*STAFF_ROLES)
def escalate_ticket(ticket_id):
    uid, role = current_user()
    notes = ((request.get_json(silent=True) or {}).get("notes") or "Manual escalation")[:255]
    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role, write=True)
        _staff_can_modify(t, uid, role)
        level = min(3, (t["escalation_level"] or 0) + 1)
        target = t["team_lead_id"]
        if level >= 2 or not target:
            cur.execute("SELECT u.user_id FROM users u JOIN roles r ON r.role_id = u.role_id "
                        "AND r.role_name = 'ADMIN' WHERE u.is_active = TRUE LIMIT 1")
            admin = cur.fetchone()
            target = admin["user_id"] if admin else target
        cur.execute(
            """INSERT INTO ticket_escalations (ticket_id, level, reason, escalated_to, notes)
               VALUES (%s, %s, 'MANUAL', %s, %s)""",
            (ticket_id, level, target, notes),
        )
        cur.execute(
            "UPDATE tickets SET is_escalated = TRUE, escalation_level = %s WHERE ticket_id = %s",
            (level, ticket_id),
        )
        notify(cur, target, ticket_id, f"Ticket {t['ticket_number']} escalated (level {level})")
        audit(cur, uid, "ESCALATE_TICKET", f"{t['ticket_number']} level {level}")
    return jsonify({"message": "Ticket escalated", "level": level}), 200


# ------------------------------------------------------------------ comments
@tickets_bp.route("/<int:ticket_id>/comments", methods=["GET"])
@role_required()
def list_comments(ticket_id):
    uid, role = current_user()
    with db_session() as cur:
        load_ticket(cur, ticket_id, uid, role)
        sql = """SELECT cm.comment_id, cm.body, cm.is_internal, cm.is_ai_generated,
                        cm.created_at, u.full_name AS author
                   FROM ticket_comments cm JOIN users u ON u.user_id = cm.author_id
                  WHERE cm.ticket_id = %s"""
        if role == "CUSTOMER":
            sql += " AND cm.is_internal = FALSE"
        cur.execute(sql + " ORDER BY cm.created_at", (ticket_id,))
        return jsonify(cur.fetchall()), 200


@tickets_bp.route("/<int:ticket_id>/comments", methods=["POST"])
@role_required()
def add_comment(ticket_id):
    """Public reply, or an internal note (staff only)."""
    uid, role = current_user()
    data = request.get_json(silent=True) or {}
    body = data.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ApiError("Comment body is required")
    is_internal = bool(data.get("is_internal", False))
    if is_internal and role == "CUSTOMER":
        raise ApiError("Customers cannot add internal notes", 403)

    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role, write=role != "CUSTOMER")
        cur.execute(
            """INSERT INTO ticket_comments (ticket_id, author_id, body, is_internal, is_ai_generated)
               VALUES (%s,%s,%s,%s,%s)""",
            (ticket_id, uid, body.strip(), is_internal, bool(data.get("is_ai_generated", False))),
        )
        comment_id = cur.lastrowid  # trigger records first_responded_at for staff replies

        if role == "CUSTOMER":
            if t["status"] == "PENDING_CUSTOMER":
                mark = hist_mark(cur, ticket_id)
                cur.execute("UPDATE tickets SET status = 'IN_PROGRESS' WHERE ticket_id = %s",
                            (ticket_id,))
                hist_stamp(cur, ticket_id, mark, uid)
            notify(cur, t["assigned_agent_id"], ticket_id,
                   f"Customer replied on {t['ticket_number']}")
        elif not is_internal:
            notify(cur, t["customer_id"], ticket_id, f"New reply on {t['ticket_number']}")
    return jsonify({"message": "Comment added", "comment_id": comment_id}), 201


@tickets_bp.route("/<int:ticket_id>/history", methods=["GET"])
@role_required()
def ticket_history(ticket_id):
    uid, role = current_user()
    with db_session() as cur:
        load_ticket(cur, ticket_id, uid, role)
        sql = """SELECT h.field_name, h.old_value, h.new_value, h.changed_at,
                        u.full_name AS changed_by
                   FROM ticket_history h LEFT JOIN users u ON u.user_id = h.changed_by
                  WHERE h.ticket_id = %s"""
        if role == "CUSTOMER":
            sql += " AND h.field_name = 'STATUS'"
        cur.execute(sql + " ORDER BY h.history_id", (ticket_id,))
        return jsonify(cur.fetchall()), 200


# ------------------------------------------------------------------ attachments
@tickets_bp.route("/<int:ticket_id>/attachments", methods=["POST"])
@role_required()
def upload_attachments(ticket_id):
    uid, role = current_user()
    files = request.files.getlist("attachments")
    if not files:
        raise ApiError("Send files in the 'attachments' form field")
    with db_session() as cur:
        load_ticket(cur, ticket_id, uid, role, write=role != "CUSTOMER")
        saved = _save_attachments(cur, ticket_id, uid, files)
    return jsonify({"message": "Uploaded", "attachments": saved}), 201


@tickets_bp.route("/attachments/<int:attachment_id>", methods=["GET"])
@role_required()
def download_attachment(attachment_id):
    uid, role = current_user()
    with db_session() as cur:
        cur.execute("SELECT * FROM ticket_attachments WHERE attachment_id = %s", (attachment_id,))
        att = cur.fetchone()
        if not att:
            raise ApiError("Attachment not found", 404)
        load_ticket(cur, att["ticket_id"], uid, role)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], att["file_path"],
        as_attachment=True, download_name=att["file_name"],
    )


# ------------------------------------------------------------------ rating (CSAT)
@tickets_bp.route("/<int:ticket_id>/rating", methods=["POST"])
@role_required("CUSTOMER")
def rate_ticket(ticket_id):
    uid, role = current_user()
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        raise ApiError("rating must be a whole number from 1 to 5")
    feedback = data.get("feedback")
    if feedback is not None and (not isinstance(feedback, str) or len(feedback) > 500):
        raise ApiError("feedback must be text up to 500 characters")

    with db_session() as cur:
        t = load_ticket(cur, ticket_id, uid, role)
        if t["status"] not in ("RESOLVED", "CLOSED"):
            raise ApiError("You can rate a ticket only after it is resolved or closed")
        cur.execute("SELECT 1 AS x FROM ticket_ratings WHERE ticket_id = %s", (ticket_id,))
        if cur.fetchone():
            raise ApiError("This ticket has already been rated", 409)
        cur.execute(
            """INSERT INTO ticket_ratings (ticket_id, customer_id, rating, feedback)
               VALUES (%s,%s,%s,%s)""",
            (ticket_id, uid, rating, feedback),
        )
        if rating <= 2:
            notify(cur, t["team_lead_id"], ticket_id,
                   f"Low CSAT ({rating}/5) on {t['ticket_number']}")
    return jsonify({"message": "Thank you for your feedback"}), 201
