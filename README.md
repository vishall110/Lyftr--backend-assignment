# Lyftr AI – Backend Assignment

**Containerized Webhook API (FastAPI)**

---

## 📌 Overview

This project is a backend service built using **Python and FastAPI** as part of the **Lyftr AI Backend Assignment**.

The service ingests WhatsApp-like messages through a secure webhook, stores them in **SQLite**, and exposes APIs for message retrieval, analytics, health checks, and metrics.

The system is designed to be:

- Secure (HMAC-SHA256 signature verification)
- Idempotent (exactly-once message ingestion)
- Observable (structured logs and metrics)
- Simple and production-style

---

## ⚙️ Tech Stack

- Python
- FastAPI
- SQLite
- Uvicorn
- Pydantic
- Prometheus-style metrics

---

## 📁 Project Structure

```
Lyftr-backend-assignment/
│
├── main.py        # Complete FastAPI application (single-file)
├── README.md      # Project documentation
```

> Note: The entire solution is intentionally implemented in a single file (`main.py`) for simplicity.

---

## 🚀 How to Run (Local Setup)

### 1️⃣ Prerequisites

- Python 3.10+
- VS Code or any code editor

---

### 2️⃣ Install Dependencies

```bash
pip install fastapi uvicorn
```

---

### 3️⃣ Set Environment Variable (IMPORTANT)

#### Windows (PowerShell)

```powershell
$env:WEBHOOK_SECRET="testsecret"
```

#### Mac / Linux

```bash
export WEBHOOK_SECRET="testsecret"
```

---

### 4️⃣ Start the Server

```bash
uvicorn main:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

---

## 🔗 API Endpoints

### ✅ Health Checks

| Endpoint            | Description                               |
| ------------------- | ----------------------------------------- |
| GET /health/live    | Confirms the app is running               |
| GET /health/ready   | Confirms DB connectivity and secret setup |

---

### 🔐 Webhook Ingestion

**POST /webhook**

- Validates HMAC-SHA256 signature
- Ensures idempotent message ingestion

**Headers**

```
Content-Type: application/json
X-Signature: <HMAC_SHA256>
```

**Request Body Example**

```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Success Response**

```json
{"status":"ok"}
```

---

### 📬 List Messages

**GET /messages**

Supports:

- Pagination (limit, offset)
- Filtering by sender (from)
- Time filtering (since)
- Text search (q)

Example:

```
/messages?limit=2&offset=0
```

---

### 📊 Stats

**GET /stats**

Returns:

- Total messages
- Unique sender count
- Messages per sender
- First and last message timestamps

---

### 📈 Metrics

**GET /metrics**

Prometheus-style metrics including:

- HTTP request counters
- Webhook processing result counters

---

## 📝 Logging

- Structured JSON logs
- One log entry per request
- Includes timestamp, request ID, path, status, latency
- Webhook logs include result and duplication info

---

## 🧠 Design Decisions

### HMAC Verification
- Signature computed using raw request body
- Compared with X-Signature header
- Invalid signature returns 401 Unauthorized

### Idempotency
- message_id is primary key in SQLite
- Duplicate messages are ignored gracefully
- API always returns 200 OK for duplicates

### Pagination
- limit and offset supported
- total count ignores pagination

---

## 🧪 Testing

APIs can be tested using:
- Browser
- Swagger UI (/docs)
- curl
- Postman

---

## 🔐 Environment Variables

| Variable         | Description                           |
| ---------------- | ------------------------------------- |
| WEBHOOK_SECRET   | Secret key for HMAC verification      |
| DATABASE_URL     | SQLite DB path (default is used)      |

---

## 🧰 Setup Used

- VS Code
- Python virtual environment
- Occasional ChatGPT assistance

---

## ✅ Status

✔ All Lyftr AI Backend Assignment requirements implemented  
✔ Ready for evaluation and submission
