from fastapi import FastAPI, Request, HTTPException, Query
from pydantic import BaseModel, Field, validator
import sqlite3, os, hmac, hashlib, json, time, uuid, re
from datetime import datetime
from typing import Optional
from collections import defaultdict

# ---------------- CONFIG ----------------

DB_PATH = "/data/app.db"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET not set")

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")

# ---------------- APP ----------------

app = FastAPI()

# ---------------- METRICS ----------------

http_requests_total = defaultdict(int)
webhook_requests_total = defaultdict(int)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    latency = int((time.time() - start) * 1000)

    http_requests_total[(request.url.path, response.status_code)] += 1

    log = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": "INFO",
        "request_id": str(uuid.uuid4()),
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "latency_ms": latency,
    }
    print(json.dumps(log))
    return response

@app.get("/metrics")
def metrics():
    lines = []
    for (path, status), count in http_requests_total.items():
        lines.append(
            f'http_requests_total{{path="{path}",status="{status}"}} {count}'
        )
    for result, count in webhook_requests_total.items():
        lines.append(
            f'webhook_requests_total{{result="{result}"}} {count}'
        )
    return "\n".join(lines)

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup():
    os.makedirs("/data", exist_ok=True)
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            from_msisdn TEXT NOT NULL,
            to_msisdn TEXT NOT NULL,
            ts TEXT NOT NULL,
            text TEXT,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()

# ---------------- MODELS ----------------

class WebhookMessage(BaseModel):
    message_id: str = Field(..., min_length=1)
    from_: str = Field(..., alias="from")
    to: str
    ts: str
    text: Optional[str] = Field(None, max_length=4096)

    @validator("from_", "to")
    def validate_e164(cls, v):
        if not E164_REGEX.match(v):
            raise ValueError("invalid e164")
        return v

    @validator("ts")
    def validate_ts(cls, v):
        if not v.endswith("Z"):
            raise ValueError("invalid timestamp")
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

# ---------------- WEBHOOK ----------------

@app.post("/webhook")
async def webhook(request: Request):
    raw_body = await request.body()

    signature = request.headers.get("X-Signature")
    if not signature:
        webhook_requests_total["invalid_signature"] += 1
        raise HTTPException(status_code=401, detail="invalid signature")

    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        webhook_requests_total["invalid_signature"] += 1
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(raw_body)
        msg = WebhookMessage(**payload)
    except Exception:
        webhook_requests_total["validation_error"] += 1
        raise

    db = get_db()
    try:
        db.execute(
            """INSERT INTO messages
            (message_id, from_msisdn, to_msisdn, ts, text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                msg.message_id,
                msg.from_,
                msg.to,
                msg.ts,
                msg.text,
                datetime.utcnow().isoformat() + "Z"
            )
        )
        db.commit()
        webhook_requests_total["created"] += 1
    except sqlite3.IntegrityError:
        webhook_requests_total["duplicate"] += 1

    return {"status": "ok"}

# ---------------- MESSAGES ----------------

@app.get("/messages")
def messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_: Optional[str] = Query(None, alias="from"),
    since: Optional[str] = None,
    q: Optional[str] = None,
):
    db = get_db()
    conditions = []
    params = []

    if from_:
        conditions.append("from_msisdn = ?")
        params.append(from_)

    if since:
        conditions.append("ts >= ?")
        params.append(since)

    if q:
        conditions.append("LOWER(text) LIKE ?")
        params.append(f"%{q.lower()}%")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM messages {where}", params
    ).fetchone()[0]

    rows = db.execute(
        f"""
        SELECT * FROM messages
        {where}
        ORDER BY ts ASC, message_id ASC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset]
    ).fetchall()

    return {
        "data": [
            {
                "message_id": r["message_id"],
                "from": r["from_msisdn"],
                "to": r["to_msisdn"],
                "ts": r["ts"],
                "text": r["text"]
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }

# ---------------- STATS ----------------

@app.get("/stats")
def stats():
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    if total == 0:
        return {
            "total_messages": 0,
            "senders_count": 0,
            "messages_per_sender": [],
            "first_message_ts": None,
            "last_message_ts": None
        }

    senders = db.execute("""
        SELECT from_msisdn AS sender, COUNT(*) AS count
        FROM messages
        GROUP BY from_msisdn
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()

    first_ts = db.execute("SELECT MIN(ts) FROM messages").fetchone()[0]
    last_ts = db.execute("SELECT MAX(ts) FROM messages").fetchone()[0]

    return {
        "total_messages": total,
        "senders_count": len(senders),
        "messages_per_sender": [
            {"from": r["sender"], "count": r["count"]}
            for r in senders
        ],
        "first_message_ts": first_ts,
        "last_message_ts": last_ts
    }

# ---------------- HEALTH ----------------

@app.get("/health/live")
def live():
    return {"status": "live"}

@app.get("/health/ready")
def ready():
    try:
        db = get_db()
        db.execute("SELECT 1")
        if not WEBHOOK_SECRET:
            raise Exception()
    except Exception:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}
