from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
import pandas as pd

from ..schemas.ml import InputFidelisation, InputForecast, InputSentiment, PricePredictRequest
from ..services import MLService
from ..db import get_engine


router = APIRouter()


@lru_cache(maxsize=1)
def get_service() -> MLService:
    return MLService()


@router.get("/")
def home() -> dict:
    return {
        "message": "EventZilla API running",
        "docs": "/docs",
        "health": "/health",
    }


# ── Role-based chatbot enforcement ───────────────────────────
_ROLE_TOPICS: dict[str, list[str]] = {
    "marketing":   ["customer loyalty","client feedback","personalized event","customer segmentation",
                    "campaign","visitor engagement","marketing kpi","retention","satisfaction",
                    "engagement","recommendation","sentiment","channel","beneficiar"],
    "quality":     ["client satisfaction","service quality","return likelihood","feedback",
                    "unusual activity","complaint","quality kpi","rating","review",
                    "negative","provider quality","satisfaction trend"],
    "operational": ["booking demand","event profile","operational","planning","traffic",
                    "unusual activity","reservation","anomaly","forecast","season",
                    "busiest","visitor flow","overload","peak"],
    "business":    ["pricing","revenue","profitability","business kpi","strategic",
                    "financial","provider performance","profit","income","earnings",
                    "cost","budget","price","quarter","forecast revenue"],
}
_DENIED_REPLY = "You do not have access to this topic. Please contact the administrator."

def _role_allowed(role: str, question: str) -> bool:
    if role == "admin" or not role:
        return True
    topics = _ROLE_TOPICS.get(role, [])
    q = question.lower()
    allowed = any(t in q for t in topics)
    if not allowed:
        print(f"[CHATBOT] DENIED role={role!r} question={question!r}")
    return allowed




def _ask_groq(message: str, db_context: str) -> str:
    import requests as _req
    import settings as _s
    GROQ_API_KEY = _s.GROQ_API_KEY
    system_prompt = (
        "You are EventZella AI, a Business Intelligence Copilot for an event management company.\n"
        "Analyze the data and provide clear insights, anomaly detection, and actionable recommendations.\n"
        "Be concise and professional. Answer in under 4 sentences when possible.\n\n"
        "=== Database Context ===\n" + db_context
    )
    try:
        resp = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": message},
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )
        data = resp.json()
        if "choices" not in data:
            return "AI error: " + data.get("error", {}).get("message", str(data))
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"AI error: {exc}"


@router.post("/chatbot")
def chatbot(body: dict, request: Request) -> dict:
    role = (request.headers.get("X-User-Role") or "").strip().lower()
    message = (body.get("message") or "").strip()

    if not _role_allowed(role, message):
        return {"reply": _DENIED_REPLY, "sql": None, "data": [],
                "type": "general", "chart_type": None, "status": "denied"}

    engine  = get_engine()

    # Fetch live KPI context
    db_context = ""
    try:
        kpi_df = pd.read_sql(
            """SELECT ROUND(SUM(final_price)::numeric,2) AS total_revenue,
                      ROUND(AVG(final_price)::numeric,2) AS avg_revenue,
                      ROUND(AVG(rating)::numeric,2)      AS avg_rating,
                      COUNT(*)                           AS total_events,
                      SUM(visitors)                      AS total_visitors,
                      SUM(reservations)                  AS total_reservations
               FROM fact_suivi_event WHERE final_price IS NOT NULL""",
            engine,
        )
        if not kpi_df.empty:
            db_context = "\n".join(f"{k}: {v}" for k, v in kpi_df.iloc[0].items())
    except Exception:
        db_context = "Database KPIs unavailable."

    # Fetch relevant data rows for chart questions
    data_records: list = []
    sql_used = None
    rtype = "general"

    # (keywords, sql, type, chart_type)
    rules = [
        (["how many reservation", "count reserv", "total reserv", "number of reserv"],
         "SELECT COUNT(*) AS total_reservations FROM dim_reservation", "kpi", None),
        (["lowest rating", "worst provider", "low rating", "poor rating"],
         """SELECT p.name_provider, ROUND(AVG(f.rating)::numeric,2) AS avg_rating, COUNT(*) AS events
            FROM fact_suivi_event f JOIN dim_provider p ON f.sk_provider = p.sk_provider
            GROUP BY p.name_provider HAVING COUNT(*) > 2 ORDER BY avg_rating ASC LIMIT 5""", "chart", "bar"),
        (["top", "provider", "best provider", "most reserv"],
         """SELECT p.name_provider, SUM(f.reservations) AS total_reservations,
                   ROUND(AVG(f.rating)::numeric,2) AS avg_rating
            FROM fact_suivi_event f JOIN dim_provider p ON f.sk_provider = p.sk_provider
            GROUP BY p.name_provider ORDER BY total_reservations DESC LIMIT 5""", "chart", "horizontalBar"),
        (["status", "reservation status", "by status"],
         "SELECT status, COUNT(*) AS count FROM dim_reservation GROUP BY status ORDER BY count DESC", "chart", "pie"),
        (["average rating", "avg rating", "mean rating", "rating"],
         """SELECT ROUND(AVG(rating)::numeric,2) AS avg_rating,
                   MIN(rating)::numeric AS min_rating, MAX(rating)::numeric AS max_rating
            FROM fact_suivi_event WHERE rating IS NOT NULL""", "kpi", None),
        (["category", "most service", "which category", "event category"],
         """SELECT c.category_name, COUNT(*) AS event_count, ROUND(AVG(f.rating)::numeric,2) AS avg_rating
            FROM fact_suivi_event f JOIN "DIM_category" c ON f.category_id = c.category_id
            GROUP BY c.category_name ORDER BY event_count DESC LIMIT 5""", "chart", "bar"),
        (["visitor", "trend", "by month", "monthly"],
         """SELECT d.year, d.month, SUM(f.visitors) AS total_visitors
            FROM fact_suivi_event f JOIN dim_date d ON f.date_event_fk = d.date_id
            GROUP BY d.year, d.month ORDER BY d.year, d.month LIMIT 12""", "chart", "line"),
        (["revenue", "total revenue", "income", "earnings"],
         """SELECT ROUND(SUM(final_price)::numeric,2) AS total_revenue,
                   ROUND(AVG(final_price)::numeric,2) AS avg_revenue_per_event, COUNT(*) AS total_events
            FROM fact_suivi_event WHERE final_price IS NOT NULL""", "kpi", None),
        (["event type", "type of event", "wedding", "corporate", "party"],
         """SELECT event_type, COUNT(*) AS count, ROUND(AVG(rating)::numeric,2) AS avg_rating
            FROM view_event_analysis GROUP BY event_type ORDER BY count DESC""", "chart", "pie"),
        (["complaint", "issue", "problem"],
         """SELECT complaint_subject, complaint_status, COUNT(*) AS count
            FROM view_event_analysis WHERE complaint_subject IS NOT NULL
            GROUP BY complaint_subject, complaint_status ORDER BY count DESC LIMIT 10""", "chart", "bar"),
        (["budget", "price", "cost"],
         """SELECT ROUND(AVG(budget)::numeric,2) AS avg_budget, ROUND(AVG(price)::numeric,2) AS avg_price,
                   ROUND(AVG(final_price)::numeric,2) AS avg_final_price FROM fact_suivi_event""", "kpi", None),
        (["season", "saison", "summer", "winter", "spring"],
         """SELECT saison, COUNT(*) AS events, ROUND(AVG(rating)::numeric,2) AS avg_rating,
                   SUM(visitors) AS total_visitors
            FROM view_event_analysis GROUP BY saison ORDER BY events DESC""", "chart", "bar"),
    ]

    msg_lower = message.lower()
    chart_type = None
    try:
        for keywords, sql, rt, ct in rules:
            if any(k in msg_lower for k in keywords):
                df = pd.read_sql(sql, engine)
                data_records = df.to_dict(orient="records")
                sql_used = sql
                rtype = rt
                chart_type = ct
                db_context += "\n\nRelevant query results:\n" + df.head(10).to_string(index=False)
                break
    except Exception:
        pass

    reply = _ask_groq(message, db_context)

    return {
        "reply":      reply,
        "sql":        sql_used,
        "data":       data_records,
        "type":       rtype,
        "chart_type": chart_type,
        "status":     "ok",
    }



@router.post("/train/price")
def train_price() -> dict:
    return get_service().train_price()


@router.post("/train/fidelisation")
def train_fidelisation() -> dict:
    return get_service().train_fidelisation()


@router.post("/train/forecast")
def train_forecast() -> dict:
    return get_service().train_forecast()


@router.post("/predict/price")
def predict_price(data: PricePredictRequest) -> dict:
    return get_service().predict_price(data)


@router.post("/predict/fidelisation")
def predict_fidelisation(data: InputFidelisation) -> dict:
    return get_service().predict_fidelisation(data)


@router.get("/categories")
def get_categories() -> list[str]:
    return get_service().get_categories()


@router.post("/predict/forecast")
def predict_forecast(data: InputForecast):
    return get_service().predict_forecast(data)


@router.post("/predict/sentiment")
def predict_sentiment(data: InputSentiment):
    return get_service().predict_sentiment(data)


@router.get("/predict/revenue-forecast")
def revenue_forecast(horizon: int = 6) -> dict:
    import numpy as np
    import pandas as pd
    from fastapi import HTTPException

    if horizon not in (4, 6, 12):
        horizon = 6

    # ── Load historical revenue from DB ──────────────────────
    try:
        engine = get_engine()
        df = pd.read_sql(
            """SELECT e.event_date, f.final_price
               FROM fact_suivi_event f
               LEFT JOIN dim_event e ON f.event_sk = e.event_sk
               WHERE e.event_date IS NOT NULL AND f.final_price IS NOT NULL""",
            engine,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

    if df.empty:
        raise HTTPException(status_code=404, detail="No revenue data found in the database.")

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df.dropna(subset=["event_date"])

    ts = (
        df.set_index("event_date")["final_price"]
        .resample("MS").sum()
        .replace(0, np.nan)
        .interpolate(method="time")
        .ffill().bfill()
    )

    if len(ts) < 3:
        raise HTTPException(status_code=422, detail="Not enough historical data to forecast.")

    # ── Fit Holt's linear trend (robust for short series) ────
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    try:
        model = ExponentialSmoothing(ts, trend="add", seasonal=None, initialization_method="estimated")
        fit = model.fit(optimized=True, remove_bias=True)
        raw = fit.forecast(horizon)
    except Exception:
        # Fallback: simple linear extrapolation
        x = np.arange(len(ts))
        slope, intercept = np.polyfit(x, ts.values, 1)
        future_x = np.arange(len(ts), len(ts) + horizon)
        raw = pd.Series(intercept + slope * future_x)

    values = np.maximum(raw.values, 0)
    start = ts.index[-1] + pd.DateOffset(months=1)
    dates = pd.date_range(start, periods=horizon, freq="MS")

    history = [
        {"date": idx.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
        for idx, v in ts.tail(12).items()
    ]
    rows = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
            for d, v in zip(dates, values)]

    return {"status": "success", "model": "Revenue Forecast", "history": history, "forecast": rows}


# ── n8n Alerts ──────────────────────────────────────────────
class AlertCreate(BaseModel):
    pipeline: str
    severity: str = "error"
    title: str
    message: str
    details: dict = {}


@router.post("/alerts")
def create_alert(alert: AlertCreate) -> dict:
    import json

    from ..db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO n8n_alerts (pipeline, severity, title, message, details)
                VALUES (:pipeline, :severity, :title, :message, :details::jsonb)
            """),
            {
                "pipeline": alert.pipeline,
                "severity": alert.severity,
                "title": alert.title,
                "message": alert.message,
                "details": json.dumps(alert.details),
            },
        )
        conn.commit()
    return {"status": "success"}


@router.get("/alerts")
def get_alerts(limit: int = 50) -> list[dict]:
    from ..db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, pipeline, severity, title, message, details, created_at, is_read
                FROM n8n_alerts
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).fetchall()
    return [
        {
            "id": r[0],
            "pipeline": r[1],
            "severity": r[2],
            "title": r[3],
            "message": r[4],
            "details": r[5],
            "created_at": str(r[6]),
            "is_read": r[7],
        }
        for r in rows
    ]


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int) -> dict:
    from ..db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE n8n_alerts SET is_read = TRUE WHERE id = :id"),
            {"id": alert_id},
        )
        conn.commit()
    return {"status": "success"}


@router.get("/alerts/unread-count")
def unread_alert_count() -> dict:
    from ..db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM n8n_alerts WHERE is_read = FALSE")
        ).scalar()
    return {"unread_count": count}

