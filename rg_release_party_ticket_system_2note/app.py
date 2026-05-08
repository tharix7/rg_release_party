import os
import re
import sqlite3
import secrets
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, Response

load_dotenv()

try:
    from twilio.rest import Client
except Exception:
    Client = None


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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-this-password")
ENABLE_WHATSAPP = os.getenv("ENABLE_WHATSAPP", "false").lower() == "true"


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
                checked_in_at TEXT,
                whatsapp_status TEXT NOT NULL DEFAULT 'not_sent'
            )
        """)
        conn.commit()


def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "").replace(".", "")
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if phone.startswith("3"):
        phone = "+39" + phone
    return phone


def valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+\d{10,15}", phone))


def generate_ticket_code() -> str:
    # Example: RG-14MAY-A7K9Q2
    return "RG-14MAY-" + secrets.token_hex(3).upper()


def count_tickets() -> int:
    with db() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()
        return row["c"]


def get_ticket_by_phone(phone: str):
    with db() as conn:
        return conn.execute("SELECT * FROM tickets WHERE phone = ?", (phone,)).fetchone()


def send_whatsapp_ticket(phone: str, name: str, code: str) -> str:
    if not ENABLE_WHATSAPP:
        return "disabled"

    if Client is None:
        return "twilio_library_missing"

    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    sender = os.getenv("TWILIO_WHATSAPP_FROM", "")

    if not sid or not token or not sender:
        return "missing_credentials"

    body = f"""RG's UNIVERSE — RELEASE PARTY

Biglietto confermato.

Nome: {name}
Codice: {code}

Giovedì 14 maggio
22:30–00:30
2Note — Via Vittorio Veneto 111, 20091 Bresso

Mostra questo messaggio all'ingresso.
"""

    try:
        client = Client(sid, token)
        client.messages.create(
            from_=sender,
            to=f"whatsapp:{phone}",
            body=body
        )
        return "sent"
    except Exception as e:
        print("WhatsApp error:", e)
        return "error"


@app.route("/", methods=["GET", "POST"])
def index():
    init_db()
    remaining = max(EVENT["max_capacity"] - count_tickets(), 0)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
        privacy = request.form.get("privacy")

        if remaining <= 0:
            flash("Lista piena: capienza massima raggiunta.", "error")
            return redirect(url_for("index"))

        if not name or len(name) < 2:
            flash("Inserisci un nome valido.", "error")
            return redirect(url_for("index"))

        if not valid_phone(phone):
            flash("Inserisci un numero WhatsApp valido, esempio: +393331234567.", "error")
            return redirect(url_for("index"))

        if privacy != "yes":
            flash("Devi accettare il trattamento dati per ricevere il ticket.", "error")
            return redirect(url_for("index"))

        existing = get_ticket_by_phone(phone)
        if existing:
            return render_template("success.html", event=EVENT, ticket=existing, already=True)

        code = generate_ticket_code()
        created_at = datetime.now().isoformat(timespec="seconds")
        status = send_whatsapp_ticket(phone, name, code)

        try:
            with db() as conn:
                conn.execute("""
                    INSERT INTO tickets (name, phone, ticket_code, created_at, whatsapp_status)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, phone, code, created_at, status))
                conn.commit()
        except sqlite3.IntegrityError:
            existing = get_ticket_by_phone(phone)
            return render_template("success.html", event=EVENT, ticket=existing, already=True)

        ticket = get_ticket_by_phone(phone)
        return render_template("success.html", event=EVENT, ticket=ticket, already=False)

    return render_template("index.html", event=EVENT, remaining=remaining)


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

    q = request.args.get("q", "").strip()
    with db() as conn:
        if q:
            tickets = conn.execute("""
                SELECT * FROM tickets
                WHERE name LIKE ? OR phone LIKE ? OR ticket_code LIKE ?
                ORDER BY id DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        else:
            tickets = conn.execute("SELECT * FROM tickets ORDER BY id DESC").fetchall()

        total = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
        checked = conn.execute("SELECT COUNT(*) AS c FROM tickets WHERE checked_in = 1").fetchone()["c"]

    return render_template("admin.html", event=EVENT, tickets=tickets, total=total, checked=checked, q=q)


@app.route("/checkin/<ticket_code>", methods=["POST"])
def checkin(ticket_code):
    init_db()
    if not session.get("admin"):
        return redirect(url_for("admin"))

    with db() as conn:
        conn.execute("""
            UPDATE tickets
            SET checked_in = 1, checked_in_at = ?
            WHERE ticket_code = ?
        """, (datetime.now().isoformat(timespec="seconds"), ticket_code))
        conn.commit()

    return redirect(url_for("admin"))


@app.route("/undo-checkin/<ticket_code>", methods=["POST"])
def undo_checkin(ticket_code):
    init_db()
    if not session.get("admin"):
        return redirect(url_for("admin"))

    with db() as conn:
        conn.execute("""
            UPDATE tickets
            SET checked_in = 0, checked_in_at = NULL
            WHERE ticket_code = ?
        """, (ticket_code,))
        conn.commit()

    return redirect(url_for("admin"))


@app.route("/export.csv")
def export_csv():
    init_db()
    if not session.get("admin"):
        return redirect(url_for("admin"))

    with db() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id ASC").fetchall()

    def generate():
        yield "id,name,phone,ticket_code,created_at,checked_in,checked_in_at,whatsapp_status\n"
        for r in rows:
            yield f'{r["id"]},"{r["name"]}",{r["phone"]},{r["ticket_code"]},{r["created_at"]},{r["checked_in"]},{r["checked_in_at"] or ""},{r["whatsapp_status"]}\n'

    return Response(generate(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=rg_release_party_tickets.csv"})


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
