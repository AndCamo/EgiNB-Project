"""
UniTo Lab — server unificato
Route:
  /             → Dashboard P.I.E.N.A.H. (occupazione posti in tempo reale)
  /aule         → Aule Libere UniTo (calendari iCal)
  /api/status   → JSON occupazione posti
  /api/aule     → JSON aule libere dai calendari UniTo
"""

import json
import os
import threading

from dotenv import load_dotenv
load_dotenv()
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import pytz
import requests
from flask import Flask, jsonify, render_template
from icalendar import Calendar

from flask import send_from_directory
import os


# ── Importa bot Telegram solo se disponibile ──────────────────────────────────
try:
    from telegram_bot import start_bot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
RESULTS_PATH = Path(__file__).parent / "../backend/output/occupation_results.json"
OVERLAP_THRESHOLD = float(os.getenv("OVERLAP_THRESHOLD", "0.3"))
TZ                = pytz.timezone("Europe/Rome")

ICAL_URLS = [
    "https://unito.prod.up.cineca.it:443/api/FiltriICal/impegniICal?id=69f9b7e8fa4980001f9ba637",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aa295783880019aef62c",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aa7354ecaf0019babe5b",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aa926e27dd001eb330c4",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aaaefa4980001f9ba458",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aac1667e0d00376d4731",
    "https://unito.prod.up.cineca.it/api/FiltriICal/impegniICal?id=69f9aad2fc0346001aaf794a",
]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — P.I.E.N.A.H. (occupazione posti)
# ══════════════════════════════════════════════════════════════════════════════

def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        return []
    with open(RESULTS_PATH, "r") as f:
        return json.load(f)


def compute_stats(results: list[dict]) -> dict:
    total    = len(results)
    occupied = sum(1 for s in results if s["occupied"] and s["seat_overlap_ratio"] > OVERLAP_THRESHOLD)
    partial  = sum(1 for s in results if s["occupied"] and s["seat_overlap_ratio"] <= OVERLAP_THRESHOLD)
    free     = sum(1 for s in results if not s["occupied"])
    return {
        "total":        total,
        "occupied":     occupied,
        "partial":      partial,
        "free":         free,
        "occupancy_pct": round((occupied + partial) / total * 100, 1) if total else 0,
        "last_updated": datetime.now().strftime("%H:%M:%S"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — Aule Libere (calendari iCal UniTo)
# ══════════════════════════════════════════════════════════════════════════════

def parse_dt(dt_raw):
    if isinstance(dt_raw, datetime):
        return dt_raw.astimezone(TZ) if dt_raw.tzinfo else TZ.localize(dt_raw)
    return TZ.localize(datetime(dt_raw.year, dt_raw.month, dt_raw.day))


def fetch_calendar(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return Calendar.from_ical(resp.content)


def normalize_aula(location_raw: str) -> str:
    loc = location_raw.lower()
    if "babbage"     in loc: return "Lab Babbage Informatica"
    if "von neumann" in loc: return "Laboratorio Von Neumann Informatica"
    if "turing"      in loc: return "Aula Turing"
    return location_raw.split(" - ")[0].strip()


# ══════════════════════════════════════════════════════════════════════════════
# Routes — pagine HTML
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Dashboard P.I.E.N.A.H. — occupazione posti in tempo reale."""
    return render_template("index.html", threshold=OVERLAP_THRESHOLD)


@app.route("/aule")
def aule_page():
    """Pagina Aule Libere DiUniTo."""
    return render_template("aule.html")

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(os.path.join(app.root_path, 'templates', 'images'), filename)



# ══════════════════════════════════════════════════════════════════════════════
# Routes — API JSON
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    """Stato occupazione posti (usato da dashboard e bot Telegram)."""
    results = load_results()
    stats   = compute_stats(results)
    return jsonify({"stats": stats, "seats": results, "threshold": OVERLAP_THRESHOLD})


@app.route("/api/aule")
def api_aule():
    """Aule libere/occupate oggi dai calendari iCal UniTo."""
    now    = datetime.now(TZ)
    today  = now.date()
    aule   = {}
    errors = []

    with ThreadPoolExecutor(max_workers=len(ICAL_URLS)) as executor:
        futures = {executor.submit(fetch_calendar, url): url for url in ICAL_URLS}
        for future in as_completed(futures):
            url = futures[future]
            try:
                cal = future.result()
            except Exception as e:
                errors.append(f"{url}: {e}")
                continue

            for component in cal.walk():
                if component.name != "VEVENT":
                    continue

                dtstart      = parse_dt(component.get("DTSTART").dt)
                dtend        = parse_dt(component.get("DTEND").dt)
                if dtstart.date() != today:
                    continue

                location_raw = str(component.get("LOCATION", "")).strip()
                summary      = str(component.get("SUMMARY",  "")).strip()
                if not location_raw:
                    continue

                nome_aula = normalize_aula(location_raw)
                if nome_aula not in aule:
                    aule[nome_aula] = {"nome": nome_aula, "impegni": []}

                impegni = aule[nome_aula]["impegni"]
                slot    = (dtstart.strftime("%H:%M"), dtend.strftime("%H:%M"), summary)
                if not any(e["inizio"] == slot[0] and e["fine"] == slot[1] and e["titolo"] == slot[2] for e in impegni):
                    impegni.append({
                        "inizio":     slot[0],
                        "fine":       slot[1],
                        "titolo":     summary,
                        "libera_ora": not (dtstart <= now < dtend),
                    })

    if not aule and errors:
        return jsonify({"error": "Tutti i calendari hanno fallito: " + "; ".join(errors)}), 500

    result = {}
    for nome_aula, data in aule.items():
        events       = sorted(data["impegni"], key=lambda e: e["inizio"])
        occupata_ora = any(not e["libera_ora"] for e in events)

        prossima_libera  = None
        prossimo_impegno = None
        if occupata_ora:
            cur = next((e for e in events if not e["libera_ora"]), None)
            if cur:
                prossima_libera = cur["fine"]
        else:
            nxt = next((e for e in events if e["inizio"] > now.strftime("%H:%M")), None)
            if nxt:
                prossimo_impegno = nxt["inizio"]

        result[nome_aula] = {
            "nome":             data["nome"],
            "occupata_ora":     occupata_ora,
            "prossima_libera":  prossima_libera,
            "prossimo_impegno": prossimo_impegno,
            "impegni":          events,
        }

    return jsonify({
        "aule":   result,
        "ora":    now.strftime("%H:%M"),
        "data":   now.strftime("%A %d %B %Y"),
        "errors": errors,
    })


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if TELEGRAM_AVAILABLE:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            bot_thread = threading.Thread(
                target=start_bot,
                args=(bot_token, "http://127.0.0.1:5001/api/status"),
                daemon=True,
            )
            bot_thread.start()
            print("✅ Telegram bot avviato in background")
        else:
            print("⚠️  TELEGRAM_BOT_TOKEN non impostato — bot non avviato")

    print("🚀 Server unificato avviato")
    print("   Locale:   http://127.0.0.1:5001")
    print("   Network:  Apri l'app usando l'IP locale del tuo PC (es. http://192.168.1.X:5001)")
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)