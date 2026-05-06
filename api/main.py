import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT, JSON_PATH, OVERLAP_THRESHOLD

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_seats() -> list[dict]:
    path = Path(__file__).parent.parent / JSON_PATH
    if not path.exists():
        raise HTTPException(status_code=503, detail="JSON non ancora disponibile")
    with open(path) as f:
        return json.load(f)


def compute_stats(seats: list[dict]) -> dict:
    total    = len(seats)
    occupied = sum(1 for s in seats if s["occupied"] and s["seat_overlap_ratio"] > OVERLAP_THRESHOLD)
    partial  = sum(1 for s in seats if s["occupied"] and s["seat_overlap_ratio"] <= OVERLAP_THRESHOLD)
    free     = total - occupied - partial
    pct      = round((occupied + partial) / total * 100, 1) if total else 0.0
    return {"total": total, "occupied": occupied, "partial": partial, "free": free, "occupancy_pct": pct}


@app.get("/api/status")
async def get_status():
    seats = load_seats()
    return {"stats": compute_stats(seats), "seats": seats, "threshold": OVERLAP_THRESHOLD}


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
