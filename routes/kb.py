from flask import Blueprint, jsonify, request

from database import db_session
from utils.helpers import audit
from utils.security import ApiError, current_user, role_required

kb_bp = Blueprint("kb", __name__)


def _fields(data, partial=False):
    out = {}
    for f in ("title", "solution"):
        if f in data or not partial:
            v = data.get(f)
            if not isinstance(v, str) or not v.strip():
                raise ApiError(f"{f} is required")
            out[f] = v.strip()
    for f in ("problem", "tags"):
        if f in data:
            out[f] = data[f]
    if "category_id" in data:
        out["category_id"] = data["category_id"]
    if "is_published" in data:
        out["is_published"] = bool(data["is_published"])
    return out


@kb_bp.route("", methods=["GET"], strict_slashes=False)
@role_required()
def search_articles():
    _, role = current_user()
    q = (request.args.get("q") or "").strip()
    category_id = request.args.get("category_id")

    where, params = [], []
    if role == "CUSTOMER":
        where.append("is_published = TRUE")
    if category_id:
        where.append("category_id = %s")
        params.append(category_id)

    if q:
        where.append("MATCH(title, problem, solution, tags) AGAINST (%s IN NATURAL LANGUAGE MODE)")
        params.append(q)
        order = ("MATCH(title, problem, solution, tags) "
                 "AGAINST (%s IN NATURAL LANGUAGE MODE) DESC")
        params_all = params + [q]
    else:
        order = "updated_at DESC"
        params_all = params

    sql = "SELECT article_id, category_id, title, problem, solution, tags, is_published, view_count, helpful_count, updated_at FROM kb_articles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order} LIMIT 50"
    with db_session() as cur:
        cur.execute(sql, params_all)
        return jsonify(cur.fetchall()), 200


@kb_bp.route("/<int:article_id>", methods=["GET"])
@role_required()
def get_article(article_id):
    _, role = current_user()
    with db_session() as cur:
        cur.execute("SELECT * FROM kb_articles WHERE article_id = %s", (article_id,))
        art = cur.fetchone()
        if not art or (role == "CUSTOMER" and not art["is_published"]):
            raise ApiError("Article not found", 404)
        cur.execute(
            "UPDATE kb_articles SET view_count = view_count + 1 WHERE article_id = %s",
            (article_id,),
        )
    return jsonify(art), 200


@kb_bp.route("", methods=["POST"], strict_slashes=False)
@role_required("ADMIN", "TEAM_LEAD")
def create_article():
    uid, _ = current_user()
    f = _fields(request.get_json(silent=True) or {})
    cols = list(f) + ["author_id"]
    vals = list(f.values()) + [uid]
    with db_session() as cur:
        cur.execute(
            f"INSERT INTO kb_articles ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))})",
            vals,
        )
        aid = cur.lastrowid
        audit(cur, uid, "CREATE_KB", f.get("title", ""))
    return jsonify({"message": "Article created", "article_id": aid}), 201


@kb_bp.route("/<int:article_id>", methods=["PUT"])
@role_required("ADMIN", "TEAM_LEAD")
def update_article(article_id):
    uid, _ = current_user()
    f = _fields(request.get_json(silent=True) or {}, partial=True)
    if not f:
        raise ApiError("Nothing to update")
    with db_session() as cur:
        cur.execute(
            f"UPDATE kb_articles SET {', '.join(k + ' = %s' for k in f)} WHERE article_id = %s",
            list(f.values()) + [article_id],
        )
        cur.execute("SELECT 1 AS x FROM kb_articles WHERE article_id = %s", (article_id,))
        if not cur.fetchone():
            raise ApiError("Article not found", 404)
        audit(cur, uid, "UPDATE_KB", str(article_id))
    return jsonify({"message": "Article updated"}), 200


@kb_bp.route("/<int:article_id>", methods=["DELETE"])
@role_required("ADMIN")
def unpublish_article(article_id):
    uid, _ = current_user()
    with db_session() as cur:
        cur.execute(
            "UPDATE kb_articles SET is_published = FALSE WHERE article_id = %s",
            (article_id,),
        )
        audit(cur, uid, "UNPUBLISH_KB", str(article_id))
    return jsonify({"message": "Article unpublished"}), 200


@kb_bp.route("/<int:article_id>/helpful", methods=["POST"])
@role_required()
def mark_helpful(article_id):
    with db_session() as cur:
        cur.execute(
            "UPDATE kb_articles SET helpful_count = helpful_count + 1 WHERE article_id = %s",
            (article_id,),
        )
    return jsonify({"message": "Thanks for your feedback"}), 200
