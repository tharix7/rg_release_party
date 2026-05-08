# RG's UNIVERSE — Release Party Ticket System

Sistema pronto per:
- registrazione RSVP
- limite capienza 100 persone
- un solo ticket per numero WhatsApp
- generazione codice biglietto univoco
- database SQLite
- pagina admin per vedere iscritti
- check-in all'ingresso
- invio WhatsApp automatico tramite Twilio, se configuri le credenziali

## Evento preconfigurato

RG's UNIVERSE — RELEASE PARTY  
Giovedì 14 maggio  
22:30–00:30  
2Note — Via Vittorio Veneto 111, 20091 Bresso  
Capienza massima: 100  
Ticket: 1 per registrazione

---

## 1. Installazione locale

Apri Terminale nella cartella del progetto e fai:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Poi apri:

```text
http://127.0.0.1:5000
```

Admin:

```text
http://127.0.0.1:5000/admin
```

Password admin di default:

```text
change-this-password
```

Cambiala dentro `.env`.

---

## 2. Configurazione WhatsApp Twilio

Nel file `.env` metti:

```env
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
ENABLE_WHATSAPP=true
```

In fase test con Twilio Sandbox, il numero `whatsapp:+14155238886` è spesso quello sandbox.
Per produzione devi collegare un vero numero WhatsApp Business.

Se `ENABLE_WHATSAPP=false`, il sistema registra comunque il ticket ma non invia WhatsApp.

---

## 3. Messa online consigliata

Soluzione semplice:
- Render.com / Railway.app per hosting Python
- Database SQLite va bene per evento piccolo
- Per produzione più seria: PostgreSQL

Comando start:

```bash
gunicorn app:app
```

---

## 4. Privacy

Il form raccoglie numeri di telefono. Tieni il link admin privato.
Aggiungi una privacy policy se lo pubblichi seriamente.
