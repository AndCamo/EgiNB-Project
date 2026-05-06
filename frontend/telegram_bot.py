"""
Telegram bot — P.I.E.N.A.H.
Comandi supportati:
  /start        — messaggio di benvenuto
  /posti        — stato completo di tutti i posti
  /liberi       — elenco posti liberi
  /occupazione  — percentuale occupazione
  /help         — lista comandi
"""

import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


THRESHOLD = 0.3


def _fetch(api_url: str) -> dict | None:
    """Fetch seats array from Arduino API and return a normalized dict."""
    try:
        r = requests.get(api_url, timeout=5)
        r.raise_for_status()
        seats = r.json()
        total    = len(seats)
        occupied = sum(1 for s in seats if s["occupied"] and s["seat_overlap_ratio"] > THRESHOLD)
        partial  = sum(1 for s in seats if s["occupied"] and s["seat_overlap_ratio"] <= THRESHOLD)
        free     = total - occupied - partial
        return {
            "seats": seats,
            "threshold": THRESHOLD,
            "stats": {
                "total": total,
                "occupied": occupied,
                "partial": partial,
                "free": free,
                "occupancy_pct": round((occupied + partial) / total * 100, 1) if total else 0.0,
                "last_updated": "—",
            },
        }
    except Exception as e:
        print(f"[bot] Errore fetch API: {e}")
        return None


def _seat_status_line(seat: dict, threshold: float) -> str:
    """Return a single formatted line for one seat."""
    sid = seat["seat_id"]
    if not seat["occupied"]:
        icon = "🟢"
        label = "libero"
    elif seat["seat_overlap_ratio"] > threshold:
        icon = "🔴"
        label = f"occupato ({seat['seat_overlap_ratio']:.0%})"
    else:
        icon = "🟡"
        label = f"parziale ({seat['seat_overlap_ratio']:.0%})"
    return f"{icon} Posto {sid:>2} — {label}"


# ── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 Benvenuto su *P.I.E.N.A.H.*!\n\n"
        "Monitoro l'occupazione dei posti in tempo reale.\n\n"
        "Comandi disponibili:\n"
        "/posti — stato di tutti i posti\n"
        "/liberi — solo i posti liberi\n"
        "/occupazione — percentuale di occupazione\n"
        "/help — questa lista"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_occupazione(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    api_url = context.bot_data["api_url"]
    data = _fetch(api_url)
    if not data:
        await update.message.reply_text("❌ Impossibile recuperare i dati. Riprova tra poco.")
        return

    s = data["stats"]
    bar_filled = round(s["occupancy_pct"] / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    text = (
        f"📊 *Occupazione aula*\n\n"
        f"`{bar}` {s['occupancy_pct']}%\n\n"
        f"🔴 Occupati:  {s['occupied']}\n"
        f"🟡 Parziali:  {s['partial']}\n"
        f"🟢 Liberi:    {s['free']}\n"
        f"📌 Totale:    {s['total']}\n\n"
        f"🕐 Aggiornato alle {s['last_updated']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_posti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    api_url = context.bot_data["api_url"]
    data = _fetch(api_url)
    if not data:
        await update.message.reply_text("❌ Impossibile recuperare i dati. Riprova tra poco.")
        return

    threshold = data["threshold"]
    seats = data["seats"]
    lines = [_seat_status_line(s, threshold) for s in seats]

    chunk_size = 30
    chunks = [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]

    for i, chunk in enumerate(chunks):
        header = f"*Stato posti* ({len(seats)} totali)\n\n" if i == 0 else ""
        await update.message.reply_text(
            header + "\n".join(chunk),
            parse_mode="Markdown",
        )


async def cmd_liberi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    api_url = context.bot_data["api_url"]
    data = _fetch(api_url)
    if not data:
        await update.message.reply_text("❌ Impossibile recuperare i dati. Riprova tra poco.")
        return

    free_seats = [s for s in data["seats"] if not s["occupied"]]

    if not free_seats:
        await update.message.reply_text("😕 Nessun posto libero al momento.")
        return

    ids = ", ".join(str(s["seat_id"]) for s in free_seats)
    text = (
        f"🟢 *Posti liberi* ({len(free_seats)} disponibili)\n\n"
        f"Posti: {ids}\n\n"
        f"🕐 {data['stats']['last_updated']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Entry point ───────────────────────────────────────────────────────────────
def start_bot(token: str, api_url: str) -> None:
    """Build and run the bot in a secondary thread (asyncio, no signal handlers)."""

    async def run():
        application = Application.builder().token(token).build()
        application.bot_data["api_url"] = api_url

        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("help", cmd_help))
        application.add_handler(CommandHandler("posti", cmd_posti))
        application.add_handler(CommandHandler("liberi", cmd_liberi))
        application.add_handler(CommandHandler("occupazione", cmd_occupazione))

        print("[bot] In ascolto su Telegram...")
        async with application:
            await application.start()
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            while True:
                await asyncio.sleep(3600)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run())
    except Exception as e:
        print(f"[bot] Errore: {e}")
    finally:
        loop.close()