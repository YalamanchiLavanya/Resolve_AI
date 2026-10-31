import re

from flask import Blueprint, jsonify, request

from database import db_session
from utils.helpers import audit, create_customer_profile
from utils.security import STAFF_ROLES, ApiError, current_user, role_required

customers_bp = Blueprint("customers", __name__)

PROFILE_SQL = """
SELECT u.user_id, u.full_name, u.email, u.phone,
       cp.account_number, cp.address, cp.city, cp.pincode,
       cp.connection_type, cp.connection_id, cp.router_model, cp.ip_address,
       cp.installation_date, cp.connection_status,
       p.plan_id, p.plan_name, p.speed_mbps, p.monthly_price,
       p.data_limit_gb, p.is_premium
  FROM users u
  JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'CUSTOMER'
  LEFT JOIN customer_profiles cp ON cp.customer_id = u.user_id
  LEFT JOIN plans p ON p.plan_id = cp.plan_id
 WHERE u.user_id = %s"""


@customers_bp.route("/plans", methods=["GET"])
def list_plans():
    with db_session() as cur:
        cur.execute("SELECT * FROM plans ORDER BY monthly_price")
        return jsonify(cur.fetchall()), 200


@customers_bp.route("/me", methods=["GET"])
@role_required("CUSTOMER")
def my_profile():
    uid, _ = current_user()
    with db_session() as cur:
        cur.execute(PROFILE_SQL, (uid,))
        row = cur.fetchone()
    if not row:
        raise ApiError("Customer not found", 404)
    return jsonify(row), 200


@customers_bp.route("", methods=["GET"], strict_slashes=False)
@role_required(*STAFF_ROLES)
def list_customers():
    q = (request.args.get("q") or "").strip()
    sql = """SELECT u.user_id, u.full_name, u.email, cp.account_number,
                    cp.pincode, cp.connection_status, p.plan_name
               FROM users u
               JOIN roles r ON r.role_id = u.role_id AND r.role_name = 'CUSTOMER'
               LEFT JOIN customer_profiles cp ON cp.customer_id = u.user_id
               LEFT JOIN plans p ON p.plan_id = cp.plan_id"""
    params = []
    if q:
        sql += " WHERE u.full_name LIKE %s OR u.email LIKE %s OR cp.account_number LIKE %s"
        params = [f"%{q}%"] * 3
    sql += " ORDER BY u.user_id LIMIT 200"
    with db_session() as cur:
        cur.execute(sql, params)
        return jsonify(cur.fetchall()), 200


@customers_bp.route("/<int:customer_id>", methods=["GET"])
@role_required(*STAFF_ROLES)
def get_customer(customer_id):
    """Customer 360: profile + plan + recent tickets."""
    with db_session() as cur:
        cur.execute(PROFILE_SQL, (customer_id,))
        profile = cur.fetchone()
        if not profile:
            raise ApiError("Customer not found", 404)
        cur.execute(
            """SELECT ticket_id, ticket_number, subject, status, priority, created_at
                 FROM tickets WHERE customer_id = %s
                ORDER BY created_at DESC LIMIT 20""",
            (customer_id,),
        )
        profile["recent_tickets"] = cur.fetchall()
    return jsonify(profile), 200


@customers_bp.route("/<int:customer_id>", methods=["PUT"])
@role_required("ADMIN", "TEAM_LEAD")
def update_customer_profile(customer_id):
    """Create or update plan / connection details."""
    uid, _ = current_user()
    data = request.get_json(silent=True) or {}

    with db_session() as cur:
        cur.execute(
            """SELECT 1 AS x FROM users u JOIN roles r ON r.role_id = u.role_id
                WHERE u.user_id = %s AND r.role_name = 'CUSTOMER'""",
            (customer_id,),
        )
        if not cur.fetchone():
            raise ApiError("Customer not found", 404)

        cur.execute(
            "SELECT 1 AS x FROM customer_profiles WHERE customer_id = %s",
            (customer_id,),
        )
        if not cur.fetchone():
            create_customer_profile(cur, customer_id, data)
            audit(cur, uid, "CREATE_PROFILE", str(customer_id))
            return jsonify({"message": "Profile created"}), 201

        allowed = {
            "plan_id": None, "address": None, "city": None, "pincode": None,
            "connection_type": ("FIBER", "WIRELESS", "CABLE"),
            "router_model": None, "ip_address": None,
            "connection_status": ("ACTIVE", "SUSPENDED", "DISCONNECTED"),
        }
        sets, params = [], []
        for field, choices in allowed.items():
            if field not in data:
                continue
            value = data[field]
            if choices and str(value).upper() not in choices:
                raise ApiError(f"{field} must be one of {', '.join(choices)}")
            if field == "pincode" and not re.fullmatch(r"\d{6}", str(value)):
                raise ApiError("Pincode must be 6 digits")
            if field == "plan_id":
                cur.execute("SELECT 1 AS x FROM plans WHERE plan_id = %s", (value,))
                if not cur.fetchone():
                    raise ApiError("Plan not found", 404)
            sets.append(f"{field} = %s")
            params.append(str(value).upper() if choices else value)
        if not sets:
            raise ApiError("No valid fields to update")
        params.append(customer_id)
        cur.execute(
            f"UPDATE customer_profiles SET {', '.join(sets)} WHERE customer_id = %s",
            params,
        )
        audit(cur, uid, "UPDATE_PROFILE", str(customer_id))
    return jsonify({"message": "Profile updated"}), 200
