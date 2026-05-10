import os
import sys
import glob
import json
import pickle
import re
import numbers
import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.neighbors import NearestNeighbors
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Make eventzilla_api importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="EventZella API")

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── /predict model loading ───────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)

def _find_latest(pattern):
    files = sorted(glob.glob(os.path.join(BASE, pattern)))
    return files[-1] if files else None

model = scaler = columns = None
try:
    model_path  = _find_latest("models/rf_model_*.pkl") or os.path.join(BASE, "rf_model.pkl")
    scaler_path = _find_latest("models/scaler_*.pkl")   or os.path.join(BASE, "scaler.pkl")
    columns_path = os.path.join(BASE, "columns.pkl")
    if os.path.exists(model_path):
        model  = _load_pickle(model_path);  print(f"✅ Model loaded: {model_path}")
    if os.path.exists(scaler_path):
        scaler = _load_pickle(scaler_path); print(f"✅ Scaler loaded: {scaler_path}")
    if os.path.exists(columns_path):
        columns = _load_pickle(columns_path)
except Exception as e:
    print(f"❌ Model load error: {e}")

# ── Cluster model loading ────────────────────────────────────
kmeans_cl = dbscan_cl = scaler_cl = pca_cl = freq_map_cl = cluster_names_cl = None
try:
    kmeans_cl       = joblib.load(os.path.join(BASE, "kmeans_model.joblib"))
    dbscan_cl       = joblib.load(os.path.join(BASE, "dbscan_model.joblib"))
    scaler_cl       = joblib.load(os.path.join(BASE, "scaler.joblib"))
    pca_cl          = joblib.load(os.path.join(BASE, "pca.joblib"))
    freq_map_cl     = joblib.load(os.path.join(BASE, "freq_map.joblib"))
    cluster_names_cl = joblib.load(os.path.join(BASE, "cluster_names.joblib"))
    print("✅ Cluster models loaded")
except Exception as e:
    print(f"❌ Cluster model load error: {e}")

# ── Chatbot: DB + Groq setup ─────────────────────────────────
from settings import DATABASE_URL as DB_URL

DB_SCHEMA = """
You are a senior BI Data Analyst for EventZella, an event management platform.
Your ONLY job is to return a single raw SQL query. No explanation. No markdown. No prose. No backticks.

Database tables and their columns:
- stg_beneficiary(id_beneficiary, first_name, last_name, email, phone)
- stg_category(id_category, name)
- stg_subcategory(id_subcategory, name, id_category)
- stg_provider(id_provider, name, service_type, email, phone, city)
- stg_service(id_service, title, price, description, id_provider, id_subcategory)
- stg_event(id_event, title, event_date, budget, type, id_beneficiary)
- stg_reservation(id_reservation, id_service, id_event, reservation_date, status, final_price)
- stg_evaluation(id_evaluation, id_reservation, rating, comment)
- stg_complaint(id_complaint, subject, description, status, id_beneficiary, id_provider)
- stg_marketing_spend(id, month, marketing_spend, new_beneficiaries)
- stg_visitors(id, date, visitors, reservations)

CRITICAL RULES:
1. Always use table aliases.
2. All numeric columns are stored as VARCHAR. Cast with ::NUMERIC before any math.
3. Return ONLY the raw SQL string. Nothing else.
4. For aggregation questions, use COUNT(*), SUM(col::NUMERIC), AVG(col::NUMERIC).
5. Always alias result columns clearly.
6. For top/bottom items, use ORDER BY and LIMIT.
7. For chart-worthy data, return multiple rows with a label column and a value column.
"""

INSIGHT_PROMPT = """
You are a concise BI analyst. Given a SQL query result, provide ONE short business insight (2-3 sentences max).
Be direct. No filler. Focus on what the number means for the business.
"""

def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    from groq import Groq
    return Groq(api_key=api_key)

def extract_sql(text_response: str) -> str:
    clean = re.sub(r"```sql|```", "", text_response).strip()
    lines = clean.splitlines()
    sql_lines, started = [], False
    for line in lines:
        upper = line.strip().upper()
        if not started and any(upper.startswith(kw) for kw in ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE"]):
            started = True
        if started:
            sql_lines.append(line)
    return "\n".join(sql_lines).strip() if sql_lines else clean

def classify_question(q: str) -> str:
    q_lower = q.lower()
    chart_kw = ["trend", "over time", "by month", "by category", "by city", "top", "breakdown", "distribution", "compare", "per"]
    kpi_kw   = ["total", "sum", "count", "average", "avg", "how many", "how much", "visitors", "reservations", "budget", "revenue", "rating", "complaints", "providers", "beneficiaries"]
    if any(k in q_lower for k in chart_kw): return "chart"
    if any(k in q_lower for k in kpi_kw):   return "kpi"
    return "general"

def get_rule_based_chatbot_query(question: str):
    q = question.lower()
    greetings = {"hi", "hello", "hey", "bonjour", "salut"}
    wellbeing = {"how are you", "how are you?", "how r u", "how is it going"}

    if q in greetings:
        return {
            "type": "general",
            "chart_type": None,
            "reply": "Hello! Ask me about revenue, reservations, providers, event categories, seasons, engagement trends, or feedback sentiment.",
            "sql": None,
            "data": [],
        }

    if q in wellbeing:
        return {
            "type": "general",
            "chart_type": None,
            "reply": "I'm ready to help with your EventZella data. Ask about revenue, reservations, categories, providers, engagement, feedback, retention, or forecasts.",
            "sql": None,
            "data": [],
        }

    if "revenue forecast" in q or ("forecast" in q and "revenue" in q):
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT TO_CHAR(e.event_date, 'YYYY-MM') AS month,
                       ROUND(SUM(f.final_price)::NUMERIC, 2) AS revenue
                FROM fact_suivi_event f
                JOIN dim_event e ON e.event_sk = f.event_sk
                WHERE e.event_date IS NOT NULL
                  AND f.final_price IS NOT NULL
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """,
        }

    if "season" in q or "saison" in q:
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT COALESCE(v.saison, 'Unknown') AS season,
                       COUNT(*) AS event_count
                FROM view_event_analysis v
                GROUP BY season
                ORDER BY event_count DESC
            """,
        }

    if "personalized event recommendation" in q or "recommendation" in q:
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT c.category_name AS recommended_category,
                       ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_rating,
                       COUNT(*) AS event_count
                FROM fact_suivi_event f
                JOIN public."DIM_category" c ON c.category_id = f.category_id
                WHERE f.rating BETWEEN 1 AND 5
                GROUP BY c.category_name
                ORDER BY avg_rating DESC, event_count DESC
                LIMIT 5
            """,
        }

    if "profitability" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT ROUND(SUM(f.final_price - f.price)::NUMERIC, 2) AS estimated_profit,
                       ROUND(AVG(f.final_price - f.price)::NUMERIC, 2) AS avg_profit_per_event,
                       ROUND(AVG(NULLIF(f.final_price, 0) - NULLIF(f.price, 0))::NUMERIC, 2) AS avg_margin_value
                FROM fact_suivi_event f
                WHERE f.final_price IS NOT NULL
                  AND f.price IS NOT NULL
            """,
        }

    if "top business kpi" in q or "business kpi" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT ROUND(SUM(f.final_price)::NUMERIC, 2) AS total_revenue,
                       ROUND(AVG(f.final_price)::NUMERIC, 2) AS avg_revenue_per_event,
                       SUM(f.reservations) AS total_reservations,
                       ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_rating
                FROM fact_suivi_event f
                WHERE f.final_price IS NOT NULL
            """,
        }

    if "pricing optimization" in q or ("pricing" in q and "optimization" in q):
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT c.category_name AS category,
                       ROUND(AVG(f.price)::NUMERIC, 2) AS avg_list_price,
                       ROUND(AVG(f.final_price)::NUMERIC, 2) AS avg_final_price
                FROM fact_suivi_event f
                JOIN public."DIM_category" c ON c.category_id = f.category_id
                WHERE f.price IS NOT NULL
                  AND f.final_price IS NOT NULL
                GROUP BY c.category_name
                ORDER BY avg_final_price DESC
                LIMIT 5
            """,
        }

    if "quality kpi" in q or ("quality" in q and "dashboard" in q):
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_client_rating,
                       MIN(f.rating) AS lowest_rating,
                       MAX(f.rating) AS highest_rating,
                       COUNT(*) FILTER (WHERE f.rating < 3) AS negative_feedback_count,
                       COUNT(*) FILTER (WHERE f.rating >= 4) AS positive_feedback_count
                FROM fact_suivi_event f
                WHERE f.rating BETWEEN 1 AND 5
            """,
        }

    if "average client rating" in q or "avg client rating" in q or "client rating" in q or "average rating" in q or "avg rating" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_client_rating,
                       COUNT(*) AS rated_events,
                       COUNT(*) FILTER (WHERE f.rating < 3) AS low_rating_events
                FROM fact_suivi_event f
                WHERE f.rating BETWEEN 1 AND 5
            """,
        }

    if ("provider" in q and ("lowest rating" in q or "lowest ratings" in q or "low rating" in q)) or "providers with lowest ratings" in q:
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT p.name_provider AS provider,
                       ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_rating,
                       COUNT(*) AS rated_events
                FROM fact_suivi_event f
                JOIN dim_provider p ON p.sk_provider = f.sk_provider
                WHERE f.rating BETWEEN 1 AND 5
                GROUP BY p.name_provider
                HAVING COUNT(*) >= 1
                ORDER BY avg_rating ASC, rated_events DESC
                LIMIT 5
            """,
        }

    if "negative feedback" in q or "negative feedback analysis" in q:
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT c.category_name AS category,
                       COUNT(*) AS negative_feedback_count,
                       ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_rating
                FROM fact_suivi_event f
                JOIN public."DIM_category" c ON c.category_id = f.category_id
                WHERE f.rating BETWEEN 1 AND 5
                  AND f.rating < 3
                GROUP BY c.category_name
                ORDER BY negative_feedback_count DESC, avg_rating ASC
                LIMIT 5
            """,
        }

    if "satisfaction trend" in q or ("satisfaction" in q and "trend" in q):
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT d.month AS month,
                       ROUND(AVG(f.rating)::NUMERIC, 2) AS avg_rating
                FROM fact_suivi_event f
                JOIN dim_date d ON d.date_id = f.date_event_fk
                WHERE f.rating BETWEEN 1 AND 5
                GROUP BY d.month
                ORDER BY d.month
                LIMIT 12
            """,
        }

    if "booking demand forecast" in q or ("booking demand" in q and "forecast" in q):
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT d.month AS month,
                       SUM(f.reservations) AS total_reservations
                FROM fact_suivi_event f
                JOIN dim_date d ON d.date_id = f.reservation_date_fk
                GROUP BY d.month
                ORDER BY d.month
                LIMIT 12
            """,
        }

    if "reservation trend" in q or "reservation trends" in q:
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT d.month AS month,
                       SUM(f.reservations) AS total_reservations
                FROM fact_suivi_event f
                JOIN dim_date d ON d.date_id = f.reservation_date_fk
                GROUP BY d.month
                ORDER BY d.month
                LIMIT 12
            """,
        }

    if "visitor flow prediction" in q or "visitor flow" in q:
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT d.month AS month,
                       SUM(f.visitors) AS total_visitors
                FROM fact_suivi_event f
                JOIN dim_date d ON d.date_id = f.date_event_fk
                GROUP BY d.month
                ORDER BY d.month
                LIMIT 12
            """,
        }

    if "operational kpi" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT COUNT(*) AS total_events,
                       SUM(f.reservations) AS total_reservations,
                       SUM(f.visitors) AS total_visitors,
                       ROUND(AVG(f.reservations)::NUMERIC, 2) AS avg_reservations_per_event,
                       ROUND(AVG(f.visitors)::NUMERIC, 2) AS avg_visitors_per_event
                FROM fact_suivi_event f
            """,
        }

    if "detect anomalies" in q or "anomalies" in q or "anomaly" in q:
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                WITH stats AS (
                    SELECT AVG(visitors) AS avg_visitors,
                           STDDEV_POP(visitors) AS std_visitors,
                           AVG(reservations) AS avg_reservations,
                           STDDEV_POP(reservations) AS std_reservations
                    FROM fact_suivi_event
                )
                SELECT f.event_sk::TEXT AS event_id,
                       f.visitors,
                       f.reservations,
                       ROUND(GREATEST(
                         ABS((f.visitors - s.avg_visitors) / NULLIF(s.std_visitors, 0)),
                         ABS((f.reservations - s.avg_reservations) / NULLIF(s.std_reservations, 0))
                       )::NUMERIC, 2) AS anomaly_score
                FROM fact_suivi_event f
                CROSS JOIN stats s
                WHERE GREATEST(
                  ABS((f.visitors - s.avg_visitors) / NULLIF(s.std_visitors, 0)),
                  ABS((f.reservations - s.avg_reservations) / NULLIF(s.std_reservations, 0))
                ) >= 2
                ORDER BY anomaly_score DESC
                LIMIT 10
            """,
        }

    if ("top" in q and "provider" in q) or ("provider" in q and "reservation" in q):
        return {
            "type": "chart",
            "chart_type": "horizontalBar",
            "sql": """
                SELECT p.name_provider AS provider,
                       SUM(f.reservations) AS total_reservations
                FROM fact_suivi_event f
                JOIN dim_provider p ON p.sk_provider = f.sk_provider
                GROUP BY p.name_provider
                ORDER BY total_reservations DESC
                LIMIT 5
            """,
        }

    if "reservation" in q and "status" in q:
        return {
            "type": "chart",
            "chart_type": "pie",
            "sql": """
                SELECT COALESCE(NULLIF(r.status, ''), 'Unknown') AS status,
                       COUNT(*) AS reservation_count
                FROM dim_reservation r
                GROUP BY status
                ORDER BY reservation_count DESC
            """,
        }

    if "total revenue" in q or "revenue" in q or "income" in q or "earnings" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT ROUND(SUM(f.final_price)::NUMERIC, 2) AS total_revenue,
                       ROUND(AVG(f.final_price)::NUMERIC, 2) AS avg_revenue_per_event,
                       COUNT(*) AS total_reservations
                FROM fact_suivi_event f
                WHERE f.final_price IS NOT NULL
            """,
        }

    if ("engagement" in q and "trend" in q) or ("visitor" in q and "trend" in q):
        return {
            "type": "chart",
            "chart_type": "line",
            "sql": """
                SELECT d.month AS month,
                       SUM(f.visitors) AS total_visitors,
                       SUM(f.reservations) AS total_reservations
                FROM fact_suivi_event f
                JOIN dim_date d ON d.date_id = f.date_event_fk
                GROUP BY d.month
                ORDER BY d.month
                LIMIT 12
            """,
        }

    if ("feedback" in q and "sentiment" in q) or "negative feedback" in q:
        return {
            "type": "chart",
            "chart_type": "pie",
            "sql": """
                WITH rated_feedback AS (
                    SELECT CASE
                             WHEN f.rating >= 4 THEN 'Positive'
                             WHEN f.rating >= 3 THEN 'Neutral'
                             ELSE 'Negative'
                           END AS sentiment
                    FROM fact_suivi_event f
                    WHERE f.rating BETWEEN 1 AND 5
                )
                SELECT sentiment, COUNT(*) AS feedback_count
                FROM rated_feedback
                GROUP BY sentiment
                ORDER BY CASE sentiment
                           WHEN 'Positive' THEN 1
                           WHEN 'Neutral' THEN 2
                           ELSE 3
                         END
            """,
        }

    if "top performing event categories" in q or ("categor" in q and ("top" in q or "most" in q)):
        return {
            "type": "chart",
            "chart_type": "bar",
            "sql": """
                SELECT c.category_name AS category,
                       COUNT(*) AS event_count
                FROM fact_suivi_event f
                JOIN public."DIM_category" c ON c.category_id = f.category_id
                GROUP BY c.category_name
                ORDER BY event_count DESC
                LIMIT 5
            """,
        }

    if "retention" in q:
        return {
            "type": "kpi",
            "chart_type": None,
            "sql": """
                SELECT COUNT(DISTINCT f.sk_beneficiary) AS active_customers,
                       COUNT(*) AS total_events,
                       ROUND(COUNT(*)::NUMERIC / NULLIF(COUNT(DISTINCT f.sk_beneficiary), 0), 2) AS events_per_customer
                FROM fact_suivi_event f
            """,
        }

    return None

def get_sql_from_ai(client, question: str, q_type: str):
    hint = " Return multiple rows with a label column and a numeric value column." if q_type == "chart" else ""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": DB_SCHEMA},
                {"role": "user",   "content": question + hint}
            ],
            temperature=0, max_tokens=500
        )
        return extract_sql(resp.choices[0].message.content.strip())
    except Exception as e:
        print(f"SQL gen error: {e}")
        return None

def run_sql(sql: str):
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)
    except Exception as e:
        print(f"SQL exec error: {e}")
        return None

def get_insight(client, question: str, result_summary: str):
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": INSIGHT_PROMPT},
                {"role": "user",   "content": f"Question: {question}\nResult: {result_summary}"}
            ],
            temperature=0.3, max_tokens=150
        )
        return resp.choices[0].message.content.strip()
    except:
        return None

def format_number(val) -> str:
    if isinstance(val, numbers.Number):
        if val >= 1_000_000: return f"{val/1_000_000:.2f}M"
        if val >= 1_000:     return f"{val:,.0f}"
        return f"{val:,.2f}"
    return str(val)

def build_chatbot_reply(question: str, q_type: str, df: pd.DataFrame) -> str:
    q = question.lower()

    if q_type == "kpi" or df.shape[0] == 1:
        values = []
        for col in df.columns:
            label = col.replace("_", " ").title()
            val = df.iloc[0][col]
            formatted = format_number(val) if isinstance(val, numbers.Number) else str(val)
            values.append(f"{label}: {formatted}")
        return "\n".join(values)

    first = df.iloc[0]
    if "recommendation" in q and {"recommended_category", "avg_rating", "event_count"}.issubset(df.columns):
        return (
            f"Top recommendation: {first['recommended_category']} "
            f"with an average rating of {format_number(first['avg_rating'])} "
            f"across {format_number(first['event_count'])} events."
        )
    if "categor" in q and {"category", "event_count"}.issubset(df.columns):
        return f"Top category: {first['category']} with {format_number(first['event_count'])} events."
    if "provider" in q and {"provider", "total_reservations"}.issubset(df.columns):
        return f"Top provider: {first['provider']} with {format_number(first['total_reservations'])} reservations."
    if "provider" in q and {"provider", "avg_rating", "rated_events"}.issubset(df.columns):
        return f"Lowest-rated provider: {first['provider']} with an average rating of {format_number(first['avg_rating'])} across {format_number(first['rated_events'])} rated events."
    if "status" in q and {"status", "reservation_count"}.issubset(df.columns):
        return f"Most common reservation status: {first['status']} with {format_number(first['reservation_count'])} reservations."
    if "negative feedback" in q and {"category", "negative_feedback_count", "avg_rating"}.issubset(df.columns):
        return f"Most negative feedback is in {first['category']}: {format_number(first['negative_feedback_count'])} low-rating events, average rating {format_number(first['avg_rating'])}."
    if ("season" in q or "saison" in q) and {"season", "event_count"}.issubset(df.columns):
        return f"Top season: {first['season']} with {format_number(first['event_count'])} events."
    if "satisfaction" in q and {"month", "avg_rating"}.issubset(df.columns):
        return f"Satisfaction trend returned {len(df)} monthly points. Latest shown month: {df.iloc[-1]['month']} with average rating {format_number(df.iloc[-1]['avg_rating'])}."
    if ("booking demand" in q or "reservation trend" in q) and {"month", "total_reservations"}.issubset(df.columns):
        return f"Reservation demand returned {len(df)} monthly points. Latest shown month: {df.iloc[-1]['month']} with {format_number(df.iloc[-1]['total_reservations'])} reservations."
    if "visitor flow" in q and {"month", "total_visitors"}.issubset(df.columns):
        return f"Visitor flow returned {len(df)} monthly points. Latest shown month: {df.iloc[-1]['month']} with {format_number(df.iloc[-1]['total_visitors'])} visitors."
    if ("anomaly" in q or "anomalies" in q) and {"event_id", "anomaly_score"}.issubset(df.columns):
        return f"Highest anomaly: event {first['event_id']} with anomaly score {format_number(first['anomaly_score'])}."
    if ("engagement" in q or "visitor" in q) and {"month", "total_visitors"}.issubset(df.columns):
        return f"Engagement trend returned {len(df)} monthly points. Latest shown month: {df.iloc[-1]['month']}."
    if "sentiment" in q and {"sentiment", "feedback_count"}.issubset(df.columns):
        return f"Dominant feedback sentiment: {first['sentiment']} with {format_number(first['feedback_count'])} feedback records."
    if "forecast" in q and {"month", "revenue"}.issubset(df.columns):
        return f"Revenue history returned {len(df)} recent monthly points. Latest month: {first['month']}."
    if "pricing" in q and {"category", "avg_final_price"}.issubset(df.columns):
        return f"Highest average final price: {first['category']} at {format_number(first['avg_final_price'])}."

    return f"Found {len(df)} results."

# ── Schemas ──────────────────────────────────────────────────
class PredictRequest(BaseModel):
    attendees: int
    duration: int

class ChatRequest(BaseModel):
    message: str

# ── Role-based topic enforcement ─────────────────────────────
ROLE_TOPICS: dict[str, list[str]] = {
    "marketing":   ["customer loyalty","client feedback","personalized event","customer segmentation",
                    "campaign","visitor engagement","marketing kpi","retention","satisfaction",
                    "engagement","recommendation","sentiment","channel","beneficiar","category",
                    "categories","event categories"],
    "quality":     ["client satisfaction","service quality","return likelihood","feedback",
                    "unusual activity","complaint","quality kpi","rating","review",
                    "negative","provider quality","satisfaction trend"],
    "operational": ["booking demand","event profile","operational","planning","traffic",
                    "unusual activity","reservation","anomaly","forecast","season",
                    "anomalies","detect anomalies","busiest","visitor flow","overload",
                    "peak","operational kpi"],
    "business":    ["pricing","revenue","profitability","business kpi","strategic",
                    "financial","provider performance","profit","income","earnings",
                    "cost","budget","price","quarter","forecast revenue"],
}
DENIED_REPLY = "You do not have access to this topic. Please contact the administrator."
AUTH_REQUIRED_REPLY = "Please sign in to use the EventZella AI Assistant."

def _role_allowed(role: str, question: str) -> bool:
    if role == "admin":
        return True
    rule = get_rule_based_chatbot_query(question)
    if rule is not None and rule.get("reply") and rule["type"] == "general":
        return True
    topics = ROLE_TOPICS.get(role, [])
    q = question.lower()
    return any(t in q for t in topics)

class ClusterRequest(BaseModel):
    budget: float = 0
    price: float = 0
    final_price: float = 0
    rating: float = 0
    visitors: float = 0
    complaint_status: str | None = None
    complaint_subject: str | None = None
    event_type: str | None = None
    reservation_status: str | None = None
    algo: str = "dbscan"

class LoyaltyRequest(BaseModel):
    price: float
    budget: float
    final_price: float
    rating: float
    visitors: float
    event_date: str
    event_type: str
    id_complaint: str | None = None

# ── Routes ───────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "message": "EventZella API is running"}


@app.post("/predict-loyalty")
def predict_loyalty_compatibility(body: LoyaltyRequest):
    try:
        dt = pd.to_datetime(body.event_date)
        data = InputFidelisation(
            price=body.price,
            budget=body.budget,
            final_price=body.final_price,
            rating=body.rating,
            visitors=body.visitors,
            marketing_spend=0,
            price_budget_ratio=body.price / (body.budget + 0.01),
            margin=body.final_price - body.price,
            has_complaint=1 if body.id_complaint else 0,
            type_encoded=0,
            season_encoded=0,
            is_weekend=1 if dt.dayofweek >= 5 else 0,
            month=dt.month
        )
        res = _get_svc().predict_fidelisation(data)
        return {
            "is_loyal": res["prediction"],
            "probability": res["probabilite_fidelite"],
            "status": "success"
        }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict")
def predict(body: PredictRequest):
    print(f"📥 Input: attendees={body.attendees}, duration={body.duration}")
    if model is None:
        return {"prediction": 0, "status": "model_not_loaded"}
    try:
        if columns is not None:
            row = dict.fromkeys(columns, 0)
            if "reservations" in row: row["reservations"] = body.attendees
            if "price" in row:        row["price"] = body.duration * 10
            X = pd.DataFrame([row])[columns].values
        else:
            X = np.array([[body.attendees, body.duration]])
        if scaler is not None:
            X = scaler.transform(X)
        result = model.predict(X)
        prediction = int(result[0])
        print(f"📤 Prediction: {prediction}")
        return {"prediction": prediction, "status": "success"}
    except Exception as e:
        print(f"❌ Predict error: {e}")
        return {"prediction": 0, "status": "error"}


@app.post("/predict-cluster")
def predict_cluster(body: ClusterRequest):
    if scaler_cl is None or pca_cl is None or kmeans_cl is None or dbscan_cl is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Cluster models not loaded")

    algo = body.algo.lower()
    cols = [
        'budget', 'price', 'final_price', 'rating', 'visitors',
        'complaint_status_bin', 'complaint_subject_freq',
        'event_type_Corporate Event', 'event_type_Private Party',
        'event_type_Wedding', 'reservation_status_cancelled',
        'reservation_status_confirmed', 'reservation_status_pending'
    ]
    row = {
        'budget': body.budget, 'price': body.price, 'final_price': body.final_price,
        'rating': body.rating, 'visitors': body.visitors,
        'complaint_status_bin': 1 if body.complaint_status == 'open' else 0,
        'complaint_subject_freq': (freq_map_cl or {}).get(body.complaint_subject or '', 0.0),
        'event_type_Corporate Event': 1 if body.event_type == 'Corporate Event' else 0,
        'event_type_Private Party': 1 if body.event_type == 'Private Party' else 0,
        'event_type_Wedding': 1 if body.event_type == 'Wedding' else 0,
        'reservation_status_cancelled': 1 if body.reservation_status == 'cancelled' else 0,
        'reservation_status_confirmed': 1 if body.reservation_status == 'confirmed' else 0,
        'reservation_status_pending': 1 if body.reservation_status == 'pending' else 0,
    }
    df_input = pd.DataFrame([row])[cols]
    print(f"Colonnes envoyées au scaler : {df_input.columns.tolist()}")
    X_scaled = scaler_cl.transform(df_input)
    X_pca = pca_cl.transform(X_scaled)

    if algo == 'dbscan':
        samples = dbscan_cl.components_
        labels = dbscan_cl.labels_[dbscan_cl.core_sample_indices_]
        nn = NearestNeighbors(n_neighbors=1).fit(samples)
        _, indices = nn.kneighbors(X_pca)
        cluster_id = int(labels[indices[0][0]])
    else:
        cluster_id = int(kmeans_cl.predict(X_pca)[0])

    names = cluster_names_cl or {0: "Client Premium", 1: "Client Potentiel", 2: "Client à Risque", -1: "Inclassable"}
    return {
        "cluster_id": cluster_id,
        "cluster_name": names.get(cluster_id, "Inconnu"),
        "algorithm": algo,
        "status": "success",
    }


# ── Delegate to eventzilla_api ───────────────────────────────
try:
    from eventzilla_api.app import create_app as _create_full_app
    from eventzilla_api.services import MLService
    from eventzilla_api.schemas.ml import (
        InputFidelisation, PricePredictRequest as _PricePredictRequest,
        InputForecast, InputSentiment
    )
    from eventzilla_api.db import get_engine as _get_engine

    _svc = None
    def _get_svc():
        global _svc
        if _svc is None:
            _svc = MLService()
        return _svc

    @app.get("/categories")
    def get_categories():
        return _get_svc().get_categories()

    @app.post("/predict/fidelisation")
    def predict_fidelisation(data: InputFidelisation):
        return _get_svc().predict_fidelisation(data)

    @app.post("/predict/price")
    def predict_price_full(data: _PricePredictRequest):
        return _get_svc().predict_price(data)

    @app.post("/train/price")
    def train_price():
        return _get_svc().train_price()

    @app.post("/train/fidelisation")
    def train_fidelisation():
        return _get_svc().train_fidelisation()

    @app.post("/train/forecast")
    def train_forecast():
        return _get_svc().train_forecast()

    @app.post("/train/deep-learning")
    def train_deep_learning():
        svc = _get_svc()
        import mlflow, mlflow.sklearn
        mlflow.set_tracking_uri("file:./mlruns")
        mlflow.set_experiment("mlp_loyalty")
        with mlflow.start_run():
            artifacts = svc._train_deep_learning_artifacts()
            svc._deep_learning_artifacts = artifacts
            mlflow.log_params({"hidden_layers": "128,64,32", "max_iter": 500, "early_stopping": True})
            mlflow.log_metrics({
                "accuracy": round(artifacts.accuracy, 4),
                "f1_score": round(artifacts.f1_value, 4),
                "auc": round(artifacts.auc, 4),
                "iterations": artifacts.iterations,
            })
            mlflow.sklearn.log_model(artifacts.model, "model")
        return {
            "status": "success", "model": "MLPClassifier(128,64,32)",
            "accuracy": round(artifacts.accuracy, 4),
            "f1_score": round(artifacts.f1_value, 4),
            "auc": round(artifacts.auc, 4),
            "iterations": artifacts.iterations,
        }

    @app.post("/predict/forecast")
    def predict_forecast(data: InputForecast):
        return _get_svc().predict_forecast(data)

    @app.post("/predict/sentiment")
    def predict_sentiment(data: InputSentiment):
        return _get_svc().predict_sentiment(data)

    @app.post("/recommend/events")
    def recommend_events(beneficiary_id: int = Query(..., ge=1), n_reco: int = Query(default=5, ge=1, le=10)):
        return _get_svc().recommend_events(beneficiary_id=beneficiary_id, n_reco=n_reco)

    @app.post("/predict/anomalies")
    def detect_anomalies():
        return _get_svc().detect_anomalies()

    @app.get("/predict/revenue-forecast")
    def revenue_forecast(horizon: int = 6):
        import os as _os
        from fastapi import HTTPException as _HTTPException

        if horizon not in (4, 6, 12):
            horizon = 6

        def _revenue_series() -> pd.Series:
            engine = _get_engine()
            frame = pd.read_sql(
                """SELECT e.event_date, f.final_price
                   FROM fact_suivi_event f
                   LEFT JOIN dim_event e ON f.event_sk = e.event_sk
                   WHERE e.event_date IS NOT NULL AND f.final_price IS NOT NULL""",
                engine,
            )
            if frame.empty:
                raise _HTTPException(status_code=404, detail="No revenue data found in the database.")

            frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce")
            frame = frame.dropna(subset=["event_date"])
            ts = (
                frame.set_index("event_date")["final_price"]
                .resample("MS").sum()
                .replace(0, np.nan)
                .interpolate(method="time")
                .ffill()
                .bfill()
            )
            if len(ts) < 3:
                raise _HTTPException(status_code=422, detail="Not enough historical data to forecast.")
            return ts

        def _history_rows(ts: pd.Series) -> list[dict[str, float | str]]:
            return [
                {"date": idx.strftime("%Y-%m-%d"), "value": round(float(value), 2)}
                for idx, value in ts.tail(12).items()
            ]

        def _comparison_best_model() -> str | None:
            path = _os.path.join(BASE, "models", "comparison_results.json")
            if not _os.path.exists(path):
                return None
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                best_model = str(data.get("best_model") or "").strip().lower()
                return best_model or None
            except Exception:
                return None

        def _load_forecast_rows(csv_path: str) -> list[dict[str, float | str]]:
            df = pd.read_csv(csv_path)
            if {"date", "value"}.issubset(df.columns):
                date_col, value_col = "date", "value"
            elif {"ds", "yhat"}.issubset(df.columns):
                date_col, value_col = "ds", "yhat"
            else:
                raise ValueError("Unsupported forecast file format.")

            rows = []
            for _, row in df.iterrows():
                rows.append(
                    {
                        "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
                        "value": round(float(row[value_col]), 2),
                    }
                )
            return rows[:horizon]

        def _inverse_boxcox(values: np.ndarray, lam: float, offset: float) -> np.ndarray:
            if abs(lam) < 1e-10:
                return np.exp(values) - offset
            base = lam * np.asarray(values) + 1
            base = np.maximum(base, 0)
            return np.power(base, 1.0 / lam) - offset

        def _forecast_from_sarima(ts: pd.Series) -> list[dict[str, float | str]]:
            payload = _load_pickle("sarima_model.pkl")
            model_obj = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
            lam = float(payload.get("boxcox_lambda", 0.0)) if isinstance(payload, dict) else 0.0
            offset = float(payload.get("offset", 1.0)) if isinstance(payload, dict) else 1.0
            forecast_t = model_obj.forecast(steps=horizon)
            forecast_orig = _inverse_boxcox(np.asarray(forecast_t.values, dtype=float), lam, offset)
            forecast_orig = np.nan_to_num(forecast_orig, nan=0.0, posinf=0.0, neginf=0.0)
            forecast_orig = np.maximum(forecast_orig, 0)
            start = ts.index[-1] + pd.DateOffset(months=1)
            dates = pd.date_range(start, periods=horizon, freq="MS")
            return [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in zip(dates, forecast_orig)
            ]

        def _forecast_from_prophet(ts: pd.Series) -> list[dict[str, float | str]]:
            model_obj = _load_pickle("prophet_model.pkl")
            future = model_obj.make_future_dataframe(periods=horizon, freq="MS")
            forecast = model_obj.predict(future).iloc[-horizon:]
            rows = []
            for _, row in forecast.iterrows():
                rows.append(
                    {
                        "date": pd.to_datetime(row["ds"]).strftime("%Y-%m-%d"),
                        "value": round(max(0.0, float(row["yhat"])), 2),
                    }
                )
            return rows

        def _forecast_from_lstm(ts: pd.Series) -> list[dict[str, float | str]]:
            model_obj = _load_pickle("mlp_model.pkl")
            scaler_obj = _load_pickle("mlp_scaler.pkl")
            ts_values = ts.to_numpy(dtype=float).reshape(-1, 1)
            ts_scaled = scaler_obj.transform(ts_values)
            look_back = 3
            last_sequence = ts_scaled[-look_back:].copy()
            predictions: list[float] = []

            for _ in range(horizon):
                next_point = model_obj.predict(last_sequence.reshape(1, look_back))[0]
                predictions.append(float(next_point))
                last_sequence = np.append(last_sequence[1:], [[next_point]], axis=0)

            forecast_values = scaler_obj.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()
            forecast_values = np.maximum(np.nan_to_num(forecast_values, nan=0.0, posinf=0.0, neginf=0.0), 0)
            start = ts.index[-1] + pd.DateOffset(months=1)
            dates = pd.date_range(start, periods=horizon, freq="MS")
            return [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in zip(dates, forecast_values)
            ]

        ts = _revenue_series()
        history = _history_rows(ts)
        best_model = _comparison_best_model()

        model_labels = {
            "sarima": "SARIMA",
            "prophet": "Prophet",
            "lstm": "LSTM (MLP Proxy)",
        }

        try:
            if best_model == "sarima":
                forecast = _forecast_from_sarima(ts)
            elif best_model == "prophet":
                forecast = _forecast_from_prophet(ts)
            elif best_model == "lstm":
                forecast = _forecast_from_lstm(ts)
            else:
                raise FileNotFoundError
            return {
                "status": "success",
                "model": model_labels.get(best_model, "Best Model"),
                "best_model": best_model,
                "history": history,
                "forecast": forecast,
                "selection_source": "models/comparison_results.json",
            }
        except Exception:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            model = ExponentialSmoothing(
                ts,
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            )
            fit = model.fit(optimized=True, remove_bias=True)
            raw = fit.forecast(horizon)
            values = np.maximum(np.asarray(raw.values, dtype=float), 0)
            start = ts.index[-1] + pd.DateOffset(months=1)
            dates = pd.date_range(start, periods=horizon, freq="MS")
            forecast = [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
                for d, v in zip(dates, values)
            ]
            return {
                "status": "success",
                "model": "Holt-Winters Fallback",
                "best_model": best_model or "fallback",
                "history": history,
                "forecast": forecast,
                "selection_source": "fallback",
            }


    @app.post("/lab/train/sarima")
    def train_sarima():
        return _get_svc().train_sarima()

    @app.post("/lab/train/prophet")
    def train_prophet():
        return _get_svc().train_prophet()

    @app.post("/lab/train/lstm")
    def train_lstm():
        return _get_svc().train_lstm()

    @app.post("/lab/train/compare")
    def compare_models():
        return _get_svc().compare_models()

    @app.post("/predict/deep-learning")
    def predict_deep_learning(data: InputFidelisation):
        return _get_svc().predict_deep_learning(data)

    from eventzilla_api.routers.lab import router as lab_router
    app.include_router(lab_router, prefix="/lab")

    print("eventzilla_api routes registered OK")
except Exception as _e:
    print(f"eventzilla_api import failed: {_e}")


@app.post("/chatbot")
def chatbot(body: ChatRequest, request: Request):
    role = (request.headers.get("X-User-Role") or "").strip().lower()
    question = body.message.strip()
    rule = get_rule_based_chatbot_query(question)

    if not role:
        return {"reply": AUTH_REQUIRED_REPLY, "sql": None, "data": [], "type": "general",
                "chart_type": None, "status": "unauthorized"}

    if not _role_allowed(role, question):
        print(f"[CHATBOT] DENIED role={role!r} question={question!r}")
        return {"reply": DENIED_REPLY, "sql": None, "data": [], "type": "general",
                "chart_type": None, "status": "denied"}

    if rule is not None and rule.get("reply"):
        return {"reply": rule["reply"], "sql": rule.get("sql"), "data": rule.get("data", []),
                "type": rule["type"], "chart_type": rule["chart_type"], "status": "success"}

    client = _get_groq_client()
    if client is None and rule is None:
        return {"reply": "Chatbot API key is missing.", "sql": None, "data": [], "type": "general",
                "chart_type": None, "status": "error"}

    if rule is not None:
        q_type = rule["type"]
        chart_type = rule["chart_type"]
        sql = rule["sql"]
    else:
        q_type = classify_question(question)
        chart_type = None
        sql = get_sql_from_ai(client, question, q_type)

    if not sql:
        return {"reply": "Sorry, I couldn't process that request.", "sql": None, "data": [], "type": q_type,
                "chart_type": chart_type, "status": "error"}

    df = run_sql(sql)

    if df is None or df.empty:
        return {"reply": "The query ran but returned no results.", "sql": sql, "data": [], "type": q_type,
                "chart_type": chart_type, "status": "success"}

    data = df.head(50).to_dict(orient="records")

    reply = build_chatbot_reply(question, q_type, df)
    insight_context = reply if q_type == "kpi" else df.head(5).to_string(index=False)
    insight = get_insight(client, question, insight_context) if client else None
    if insight:
        reply += f"\n\n{insight}"

    return {"reply": reply, "sql": sql, "data": data, "type": q_type,
            "chart_type": chart_type, "status": "success"}
