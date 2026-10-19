"""Small Flask voting app for Agora."""

from __future__ import annotations

import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pymysql
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
    )
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DB_HOST=os.environ.get("DB_HOST"),
        DB_NAME=os.environ.get("DB_NAME"),
        DB_USER=os.environ.get("DB_USER"),
        DB_PASSWORD=os.environ.get("DB_PASSWORD"),
        SITE_NAME=os.environ.get("SITE_NAME", "Agora"),
    )
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY in the environment before starting Agora.")

    def connection() -> pymysql.connections.Connection:
        if "db" not in g:
            required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
            missing = [key for key in required if app.config[key] is None]
            if missing:
                raise RuntimeError(f"Missing database environment variables: {', '.join(missing)}")
            g.db = pymysql.connect(
                host=app.config["DB_HOST"],
                user=app.config["DB_USER"],
                password=app.config["DB_PASSWORD"],
                database=app.config["DB_NAME"],
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=False,
            )
        return g.db

    @app.teardown_appcontext
    def close_connection(_error: BaseException | None = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def template_values() -> dict[str, Any]:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"site_name": app.config["SITE_NAME"], "csrf_token": session["csrf_token"]}

    @app.before_request
    def protect_post_requests() -> None:
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected, supplied):
                abort(400, description="Your form expired. Please reload and try again.")

    def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if not session.get("user_id"):
                flash("Please log in to vote.", "info")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if session.get("role") != "ADMIN":
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    def poll_is_open(poll: dict[str, Any], now: datetime | None = None) -> bool:
        moment = now or datetime.now()
        return poll["start_date"] <= moment <= poll["end_date"]

    def load_poll(poll_id: int) -> dict[str, Any] | None:
        db = connection()
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT p.poll_id, p.title, p.description, p.start_date, p.end_date,
                          p.created_at, u.username AS creator
                   FROM polls AS p JOIN users AS u ON u.user_id = p.created_by
                   WHERE p.poll_id = %s""",
                (poll_id,),
            )
            poll = cursor.fetchone()
            if poll is None:
                return None
            cursor.execute(
                """SELECT o.option_id, o.label, COUNT(v.vote_id) AS votes
                   FROM poll_options AS o
                   LEFT JOIN votes AS v
                     ON v.option_id = o.option_id AND v.poll_id = o.poll_id
                   WHERE o.poll_id = %s
                   GROUP BY o.option_id, o.label
                   ORDER BY o.option_id""",
                (poll_id,),
            )
            poll["options"] = cursor.fetchall()
            cursor.execute(
                "SELECT COUNT(*) AS total FROM votes WHERE poll_id = %s", (poll_id,)
            )
            poll["total_votes"] = cursor.fetchone()["total"]
            poll["user_vote"] = None
            if session.get("user_id"):
                cursor.execute(
                    "SELECT option_id FROM votes WHERE user_id = %s AND poll_id = %s",
                    (session["user_id"], poll_id),
                )
                vote = cursor.fetchone()
                poll["user_vote"] = vote["option_id"] if vote else None
        return poll

    @app.get("/health")
    def health() -> str:
        return "ok"

    @app.get("/")
    def home() -> str:
        db = connection()
        with db.cursor() as cursor:
            cursor.execute(
                """SELECT p.poll_id, p.title, p.description, p.start_date, p.end_date,
                          COUNT(v.vote_id) AS total_votes
                   FROM polls AS p
                   LEFT JOIN votes AS v ON v.poll_id = p.poll_id
                   GROUP BY p.poll_id
                   ORDER BY p.created_at DESC"""
            )
            polls = cursor.fetchall()
        now = datetime.now()
        for poll in polls:
            poll["is_open"] = poll_is_open(poll, now)
            poll["is_upcoming"] = now < poll["start_date"]
        return render_template("home.html", polls=polls)

    @app.route("/register", methods=["GET", "POST"])
    def register() -> str | Any:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not re.fullmatch(r"[A-Za-z0-9_]{3,50}", username):
                flash("Choose a username with 3–50 letters, numbers, or underscores.", "error")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Please enter a valid email address.", "error")
            elif len(password) < 8:
                flash("Your password needs at least 8 characters.", "error")
            else:
                db = connection()
                try:
                    with db.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                            (username, email, generate_password_hash(password)),
                        )
                        user_id = cursor.lastrowid
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    flash("That username or email is already registered.", "error")
                else:
                    session.clear()
                    session.update(user_id=user_id, username=username, role="USER")
                    flash("Welcome to Agora! Your account is ready. 🌷", "success")
                    return redirect(url_for("home"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str | Any:
        next_url = request.args.get("next", "")
        if request.method == "POST":
            identity = request.form.get("identity", "").strip()
            password = request.form.get("password", "")
            with connection().cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, username, password_hash, role FROM users "
                    "WHERE username = %s OR email = %s LIMIT 1",
                    (identity, identity.lower()),
                )
                user = cursor.fetchone()
            if not user or not check_password_hash(user["password_hash"], password):
                flash("Those details didn't match. Try again?", "error")
            else:
                session.clear()
                session.update(
                    user_id=user["user_id"], username=user["username"], role=user["role"]
                )
                flash(f"Welcome back, {user['username']}! ✨", "success")
                target = request.form.get("next", next_url)
                if target.startswith("/") and not target.startswith("//"):
                    return redirect(target)
                return redirect(url_for("home"))
        return render_template("login.html", next_url=next_url)

    @app.post("/logout")
    def logout() -> Any:
        session.clear()
        flash("See you soon! 👋", "success")
        return redirect(url_for("home"))

    @app.get("/poll/<int:poll_id>")
    def poll_detail(poll_id: int) -> str:
        poll = load_poll(poll_id)
        if poll is None:
            abort(404)
        now = datetime.now()
        poll["is_open"] = poll_is_open(poll, now)
        poll["is_upcoming"] = now < poll["start_date"]
        poll["show_results"] = poll["user_vote"] is not None or now > poll["end_date"]
        for option in poll["options"]:
            option["percentage"] = (
                round(option["votes"] * 100 / poll["total_votes"])
                if poll["total_votes"]
                else 0
            )
        can_vote = bool(
            session.get("user_id") and poll["is_open"] and poll["user_vote"] is None
        )
        return render_template("poll.html", poll=poll, can_vote=can_vote)

    @app.post("/poll/<int:poll_id>/vote")
    @login_required
    def vote(poll_id: int) -> Any:
        try:
            option_id = int(request.form.get("option_id", ""))
        except (TypeError, ValueError):
            flash("Pick one of the choices before voting.", "error")
            return redirect(url_for("poll_detail", poll_id=poll_id))

        db = connection()
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    "SELECT start_date, end_date FROM polls WHERE poll_id = %s FOR UPDATE",
                    (poll_id,),
                )
                poll = cursor.fetchone()
                if poll is None:
                    abort(404)
                cursor.execute("SELECT NOW() AS current_time")
                now = cursor.fetchone()["current_time"]
                if not poll_is_open(poll, now):
                    db.rollback()
                    flash("This poll isn't open for voting right now.", "error")
                    return redirect(url_for("poll_detail", poll_id=poll_id))
                cursor.execute(
                    "SELECT option_id FROM poll_options WHERE poll_id = %s AND option_id = %s",
                    (poll_id, option_id),
                )
                if cursor.fetchone() is None:
                    db.rollback()
                    flash("That choice doesn't belong to this poll.", "error")
                    return redirect(url_for("poll_detail", poll_id=poll_id))
                cursor.execute(
                    "INSERT INTO votes (user_id, poll_id, option_id) VALUES (%s, %s, %s)",
                    (session["user_id"], poll_id, option_id),
                )
            db.commit()
        except IntegrityError:
            db.rollback()
            flash("You've already voted in this poll. Thanks! 💛", "info")
            return redirect(url_for("poll_detail", poll_id=poll_id))

        flash("Thanks for voting! 🎉", "success")
        return redirect(url_for("poll_detail", poll_id=poll_id))

    @app.get("/admin")
    @admin_required
    def admin() -> str:
        with connection().cursor() as cursor:
            cursor.execute(
                """SELECT p.poll_id, p.title, p.start_date, p.end_date,
                          COUNT(v.vote_id) AS total_votes
                   FROM polls AS p LEFT JOIN votes AS v ON v.poll_id = p.poll_id
                   GROUP BY p.poll_id ORDER BY p.created_at DESC"""
            )
            polls = cursor.fetchall()
        now = datetime.now()
        for poll in polls:
            poll["is_open"] = poll_is_open(poll, now)
            poll["is_upcoming"] = now < poll["start_date"]
            poll["can_close"] = now <= poll["end_date"]
        return render_template(
            "admin.html",
            polls=polls,
            now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
            default_end=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
        )

    @app.post("/admin/polls")
    @admin_required
    def create_poll() -> Any:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        option_labels = [label.strip() for label in request.form.getlist("options")]
        option_labels = [label for label in option_labels if label]
        try:
            start_date = datetime.fromisoformat(request.form.get("start_date", ""))
            end_date = datetime.fromisoformat(request.form.get("end_date", ""))
        except ValueError:
            flash("Please choose valid start and end times.", "error")
            return redirect(url_for("admin"))
        if not title or len(title) > 160:
            flash("Give your poll a title (up to 160 characters).", "error")
        elif len(description) > 5000:
            flash("Keep the description under 5,000 characters.", "error")
        elif len(option_labels) < 2:
            flash("Add at least two non-empty choices.", "error")
        elif any(len(label) > 160 for label in option_labels):
            flash("Each choice must be 160 characters or fewer.", "error")
        elif start_date >= end_date:
            flash("The poll end time must be after its start time.", "error")
        else:
            db = connection()
            try:
                with db.cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO polls
                           (title, description, start_date, end_date, created_by)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (title, description, start_date, end_date, session["user_id"]),
                    )
                    poll_id = cursor.lastrowid
                    cursor.executemany(
                        "INSERT INTO poll_options (label, poll_id) VALUES (%s, %s)",
                        [(label, poll_id) for label in option_labels],
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
            flash("Your new poll is ready to go! 🌈", "success")
            return redirect(url_for("poll_detail", poll_id=poll_id))
        return redirect(url_for("admin"))

    @app.post("/admin/polls/<int:poll_id>/close")
    @admin_required
    def close_poll(poll_id: int) -> Any:
        with connection().cursor() as cursor:
            cursor.execute(
                """UPDATE polls
                   SET start_date = LEAST(start_date, NOW()),
                       end_date = LEAST(end_date, NOW())
                   WHERE poll_id = %s""",
                (poll_id,),
            )
            changed = cursor.rowcount
            if not changed:
                cursor.execute("SELECT poll_id FROM polls WHERE poll_id = %s", (poll_id,))
                exists = cursor.fetchone() is not None
            else:
                exists = True
        connection().commit()
        if not exists:
            flash("We couldn't find that poll.", "error")
        else:
            flash("Poll closed. Thanks for hosting! 🌙", "success")
        return redirect(url_for("admin"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
