import re

from flask import request

from .security import ApiError

CONNECTION_PREFIX = {"FIBER": "FTTH", "WIRELESS": "WRL", "CABLE": "CBL"}


def audit(cur, user_id, action, details=None):
    cur.execute(
        """INSERT INTO audit_logs (user_id, action, details, ip_address)
           VALUES (%s, %s, %s, %s)""",
        (user_id, action, (details or "")[:500], request.remote_addr),
    )


def notify(cur, user_id, ticket_id, message):
    if user_id:
        cur.execute(
            """INSERT INTO notifications (user_id, ticket_id, message)
               VALUES (%s, %s, %s)""",
            (user_id, ticket_id, message[:255]),
        )


def hist_mark(cur, ticket_id):
    """Remember the newest history id so we can stamp rows the triggers add."""
    cur.execute(
        "SELECT COALESCE(MAX(history_id), 0) AS m FROM ticket_history WHERE ticket_id = %s",
        (ticket_id,),
    )
    return cur.fetchone()["m"]


def hist_stamp(cur, ticket_id, mark, user_id):
    """Record WHO made the change on history rows created by DB triggers."""
    cur.execute(
        """UPDATE ticket_history SET changed_by = %s
           WHERE ticket_id = %s AND history_id > %s AND changed_by IS NULL""",
        (user_id, ticket_id, mark),
    )


def load_ticket(cur, ticket_id, uid, role, write=False):
    """Fetch a ticket and enforce role-based access. Raises ApiError."""
    cur.execute(
        """SELECT t.*, tm.team_lead_id
             FROM tickets t
             LEFT JOIN teams tm ON tm.team_id = t.team_id
            WHERE t.ticket_id = %s""",
        (ticket_id,),
    )
    t = cur.fetchone()
    if not t:
        raise ApiError("Ticket not found", 404)

    ok = False
    if role == "ADMIN":
        ok = True
    elif role == "CUSTOMER":
        ok = t["customer_id"] == uid
    elif role == "TEAM_LEAD":
        ok = t["team_lead_id"] == uid
    elif role == "SUPPORT_AGENT":
        if t["assigned_agent_id"] == uid:
            ok = True
        elif not write and t["assigned_agent_id"] is None and t["team_id"]:
            cur.execute(
                "SELECT 1 AS x FROM team_members WHERE team_id = %s AND user_id = %s",
                (t["team_id"], uid),
            )
            ok = cur.fetchone() is not None
    if not ok:
        raise ApiError("You do not have access to this ticket", 403)
    return t


def find_kb(cur, text, category_id=None, limit=3):
    """Knowledge-base matching: MySQL FULLTEXT relevance, category fallback."""
    cur.execute(
        """SELECT article_id, title, solution, category_id,
                  MATCH(title, problem, solution, tags)
                  AGAINST (%s IN NATURAL LANGUAGE MODE) AS score
             FROM kb_articles
            WHERE is_published = TRUE
              AND MATCH(title, problem, solution, tags)
                  AGAINST (%s IN NATURAL LANGUAGE MODE)
            ORDER BY score DESC LIMIT %s""",
        (text, text, limit),
    )
    rows = cur.fetchall()
    if not rows and category_id:
        cur.execute(
            """SELECT article_id, title, solution, category_id, 0 AS score
                 FROM kb_articles
                WHERE is_published = TRUE AND category_id = %s LIMIT %s""",
            (category_id, limit),
        )
        rows = cur.fetchall()
    return rows


def create_customer_profile(cur, uid, d: dict):
    """Insert a customer_profiles row from a dict of fields."""
    try:
        plan_id = int(d.get("plan_id") or 0)
    except (TypeError, ValueError):
        raise ApiError("Valid plan_id is required")
    cur.execute("SELECT 1 AS x FROM plans WHERE plan_id = %s", (plan_id,))
    if not cur.fetchone():
        raise ApiError("Plan not found", 404)

    address = (d.get("address") or "").strip()
    pincode = str(d.get("pincode") or "").strip()
    if not address:
        raise ApiError("Address is required")
    if not re.fullmatch(r"\d{6}", pincode):
        raise ApiError("Pincode must be 6 digits")

    ctype = str(d.get("connection_type") or "FIBER").upper()
    if ctype not in CONNECTION_PREFIX:
        raise ApiError("connection_type must be FIBER, WIRELESS or CABLE")

    cur.execute(
        """INSERT INTO customer_profiles
              (customer_id, plan_id, account_number, address, city, pincode,
               connection_type, connection_id, router_model, ip_address,
               installation_date)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURDATE())""",
        (
            uid, plan_id, f"ACC9{uid:05d}", address, d.get("city"), pincode,
            ctype, f"{CONNECTION_PREFIX[ctype]}-AP-{900000 + uid}",
            d.get("router_model"), d.get("ip_address"),
        ),
    )
