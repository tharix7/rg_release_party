# SOSTITUISCI IL TUO app.py CON QUESTO

import os
import re
import sqlite3
import secrets
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

EVENT = {
    "name": os.getenv("EVENT_NAME", "RG's UNIVERSE — RELEASE PARTY"),
    "date": os.getenv("EVENT_DATE", "Giovedì 14 maggio"),
    "time": os.getenv("EVENT_TIME", "22:30–00:30"),
    "location": os.getenv("EVENT_LOCATION", "2Note — Via Vittorio Veneto 111, 20091 Bresso"),
    "max_capacity": int(os.getenv("MAX_CAPACITY", "100")),
}

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "rgadmin2026")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                ticket_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                checked_in INTEGER NOT NULL DEFAULT 0,
                checked_in_at TEXT
            )
        """)
        conn.commit()


def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("3"):
        phone = "+39" + phone
    return phone


def valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+\d{10,15}", phone))


def generate_ticket_code() -> str:
    return "RG-14MAY-" + secrets.token_hex(3).upper()


def count_tickets():
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()
        return row["c"]


def get_ticket_by_phone(phone):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE phone = ?",
            (phone,)
        ).fetchone()


@app.route("/", methods=["GET", "POST"])
def index():
    init_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))

        if not name:
            flash("Inserisci un nome valido.", "error")
            return redirect(url_for("index"))

        if not valid_phone(phone):
            flash("Numero non valido.", "error")
            return redirect(url_for("index"))

        existing = get_ticket_by_phone(phone)

        if existing:
            return render_template(
                "success.html",
                event=EVENT,
                ticket=existing,
                already=True
            )

        code = generate_ticket_code()

        with db() as conn:
            conn.execute("""
                INSERT INTO tickets
                (name, phone, ticket_code, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                name,
                phone,
                code,
                datetime.now().isoformat(timespec="seconds")
            ))
            conn.commit()

        ticket = get_ticket_by_phone(phone)

        return render_template(
            "success.html",
            event=EVENT,
            ticket=ticket,
            already=False
        )

    return render_template(
        "index.html",
        event=EVENT
    )


@app.route("/admin", methods=["GET", "POST"])
def admin():
    init_db()

    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Password errata.", "error")

    if not session.get("admin"):
        return render_template("login.html")

    with db() as conn:
        tickets = conn.execute(
            "SELECT * FROM tickets ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "admin.html",
        event=EVENT,
        tickets=tickets
    )


@app.route("/checkin/<ticket_code>", methods=["POST"])
def checkin(ticket_code):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    with db() as conn:
        conn.execute("""
            UPDATE tickets
            SET checked_in = 1,
                checked_in_at = ?
            WHERE ticket_code = ?
        """, (
            datetime.now().isoformat(timespec="seconds"),
            ticket_code
        ))
        conn.commit()

    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
