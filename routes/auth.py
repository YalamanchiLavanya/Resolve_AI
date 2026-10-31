import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash, generate_password_hash
from database import db_session
from utils.helpers import audit, create_customer_profile
from utils.security import ApiError, current_user, role_required

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STAFF_CREATABLE = ("SUPPORT_AGENT", "TEAM_LEAD", "ADMIN")


def _validate_user_fields(data):
    name = data.get("name") or data.get("full_name")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(name, str) or not name.strip():
        raise ApiError("Name is required")
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        raise ApiError("A valid email is required")
    if not isinstance(password, str) or len(password) < 8:
        raise ApiError("Password must be at least 8 characters")
    return name.strip(), email.strip().lower(), password


def _insert_user(cur, role_name, name, email, password, phone=None):
    cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        raise ApiError("This email is already registered", 409)
    cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (role_name,))
    role = cur.fetchone()
    if not role:
        raise ApiError("Role not found", 400)
    cur.execute(
        """INSERT INTO users (role_id, full_name, email, password_hash, phone)
           VALUES (%s, %s, %s, %s, %s)""",
        (role["role_id"], name, email, generate_password_hash(password), phone),
    )
    return cur.lastrowid


@auth_bp.route("/register", methods=["POST"])
def register():
    """Public self-registration. Always creates a CUSTOMER."""
    data = request.get_json(silent=True) or {}
    name, email, password = _validate_user_fields(data)

    with db_session() as cur:
        uid = _insert_user(cur, "CUSTOMER", name, email, password, data.get("phone"))
        # Optional profile at sign-up (plan + connection details)
        if data.get("plan_id") and data.get("address") and data.get("pincode"):
            create_customer_profile(cur, uid, data)
        audit(cur, uid, "REGISTER", email)

    return jsonify({"message": "Registration successful", "user_id": uid}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not email.strip():
        raise ApiError("Email is required")
    if not isinstance(password, str) or not password:
        raise ApiError("Password is required")
    email = email.strip().lower()

    with db_session() as cur:
        cur.execute(
            """SELECT u.user_id, u.full_name, u.email, u.password_hash,
                      u.is_active, r.role_name
                 FROM users u JOIN roles r ON r.role_id = u.role_id
                WHERE u.email = %s""",
            (email,),
        )
        user = cur.fetchone()

        valid = bool(
            user and user["is_active"]
            and check_password_hash(user["password_hash"], password)
        )
        if not valid:
            audit(cur, user["user_id"] if user else None, "LOGIN_FAILED", email)
            # commit the audit row, then respond (no exception => commit)
            return jsonify({"error": "Invalid email or password"}), 401

        cur.execute(
            "UPDATE users SET last_login = NOW() WHERE user_id = %s",
            (user["user_id"],),
        )
        audit(cur, user["user_id"], "LOGIN", email)

    token = create_access_token(
        identity=str(user["user_id"]), additional_claims={"role": user["role_name"]}
    )
    return jsonify({
        "message": "Login successful",
        "access_token": token,
        "user": {
            "user_id": user["user_id"],
            "name": user["full_name"],
            "email": user["email"],
            "role": user["role_name"],
        },
    }), 200


@auth_bp.route("/me", methods=["GET"])
@role_required()
def me():
    uid, _ = current_user()
    with db_session() as cur:
        cur.execute(
            """SELECT u.user_id, u.full_name, u.email, u.phone, r.role_name AS role
                 FROM users u JOIN roles r ON r.role_id = u.role_id
                WHERE u.user_id = %s""",
            (uid,),
        )
        user = cur.fetchone()
    if not user:
        raise ApiError("User not found", 404)
    return jsonify(user), 200


# ------------------------------------------------------------ user admin
@auth_bp.route("/users", methods=["POST"])
@role_required("ADMIN")
def create_staff_user():
    """Admin creates agents, team leads or other admins."""
    admin_id, _ = current_user()
    data = request.get_json(silent=True) or {}
    name, email, password = _validate_user_fields(data)
    role_name = str(data.get("role", "")).upper()
    if role_name not in STAFF_CREATABLE:
        raise ApiError(f"role must be one of {', '.join(STAFF_CREATABLE)}")

    with db_session() as cur:
        uid = _insert_user(cur, role_name, name, email, password, data.get("phone"))
        team_id = data.get("team_id")
        if team_id:
            cur.execute(
                "INSERT INTO team_members (team_id, user_id) VALUES (%s, %s)",
                (team_id, uid),
            )
        audit(cur, admin_id, "CREATE_USER", f"{email} as {role_name}")
    return jsonify({"message": "User created", "user_id": uid}), 201


@auth_bp.route("/users", methods=["GET"])
@role_required("ADMIN", "TEAM_LEAD")
def list_users():
    role = request.args.get("role")
    sql = """SELECT u.user_id, u.full_name, u.email, u.phone, u.is_active,
                    u.last_login, r.role_name AS role
               FROM users u JOIN roles r ON r.role_id = u.role_id"""
    params = []
    if role:
        sql += " WHERE r.role_name = %s"
        params.append(role.upper())
    sql += " ORDER BY u.user_id"
    with db_session() as cur:
        cur.execute(sql, params)
        return jsonify(cur.fetchall()), 200


@auth_bp.route("/users/<int:user_id>/active", methods=["PATCH"])
@role_required("ADMIN")
def set_user_active(user_id):
    admin_id, _ = current_user()
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("is_active"), bool):
        raise ApiError("is_active (true/false) is required")
    if user_id == admin_id and not data["is_active"]:
        raise ApiError("You cannot deactivate yourself")
    with db_session() as cur:
        cur.execute(
            "UPDATE users SET is_active = %s WHERE user_id = %s",
            (data["is_active"], user_id),
        )
        if cur.rowcount == 0:
            cur.execute("SELECT 1 AS x FROM users WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                raise ApiError("User not found", 404)
        audit(cur, admin_id, "SET_USER_ACTIVE", f"{user_id}={data['is_active']}")
    return jsonify({"message": "User updated"}), 200
