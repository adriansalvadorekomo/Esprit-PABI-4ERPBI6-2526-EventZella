# EventZella

**EventZella** is a full-stack decision intelligence platform for event management businesses. It combines a modern Angular frontend, a FastAPI + Flask microservices backend, automated ML pipelines, and n8n workflow automation — all orchestrated via Docker.

Built as a capstone project by the 4ERP BI6 team (Esprit, 2025–2026).

---

## Architecture Overview

```
┌──────────┐     ┌───────────┐     ┌──────────┐
│  Angular  │────▶│  FastAPI  │────▶│ Postgres │
│  Frontend │     │  (port 8000)    │          │
│  (port 4200)    ├───────────┤     └──────────┘
│           │     │  Flask    │
│           │     │  (port 5000)    ┌──────────┐
│           │     ├───────────┤────▶│   n8n    │
│           │     │  MLflow   │     │ (port 5678)
└──────────┘     │  (port 5001)    └──────────┘
                 └───────────┘
                 ┌──────────┐
                 │ Prometheus│    ┌──────────┐
                 │ (port 9090)───▶│  Grafana │
                 └──────────┘    │ (port 3000)
                                 └──────────┘
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

### Environment

Copy the environment template and fill in your values:

```bash
cp backend/.env.example backend/.env
```

Key variables:

| Variable | Description |
|---|---|
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `GROQ_API_KEY` | API key for the AI assistant |

### Full Stack (Docker)

```bash
docker compose up --build
```

This starts all services: postgres, fastapi, flask, frontend, n8n, prometheus, and grafana.

### Frontend Only (Development)

```bash
cd eventzilla-front
npm install
ng serve
```

Opens at `http://localhost:4200/`.

### Backend Only (Development)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

---

## Project Structure

```
├── backend/                  # FastAPI + Flask ML backend
│   ├── api/                  # FastAPI routes and models
│   ├── eventzilla_api/       # SQL queries and business logic
│   ├── models/               # Trained ML models (.pkl, .joblib)
│   ├── app.py                # Flask entry point (clustering)
│   ├── main.py               # Alternative entry point
│   ├── train*.py             # Training scripts
│   └── requirements.txt
│
├── eventzilla-front/         # Angular 20 frontend
│   └── src/app/
│       ├── components/       # Reusable components
│       │   ├── header.component.ts
│       │   ├── footer.component.ts
│       │   ├── chatbot.component.ts
│       │   ├── forecast-chart.component.ts
│       │   └── cluster-chart.component.ts   # Three.js 3D visualisation
│       ├── pages/
│       │   └── home.component.ts/html/css   # Main dashboard page
│       ├── services/         # API, Auth, Theme services
│       └── models/           # TypeScript interfaces
│
├── dags/                     # Airflow DAGs (if applicable)
├── data/                     # Data files
├── docker/                   # Docker config files
├── jobs/                     # ETL / batch job scripts
├── models/                   # Additional model artifacts
├── scripts/                  # Utility scripts
│
├── n8n_workflow_*.json       # n8n workflow exports
├── docker-compose.yml        # Full stack orchestration
├── backend.Dockerfile        # Backend image
└── frontend.Dockerfile       # Frontend image (Nginx)
```

---

## Frontend — Decision Tools

The platform offers **10 tools** designed for non-technical stakeholders:

| Tool | What it does |
|---|---|
| **Smart Event Pricing** | Estimates the best price for your event based on its characteristics |
| **Client Return Likelihood** | Predicts whether a client will come back and book again |
| **Client Loyalty Check** | Quick yes/no answer on client loyalty with confidence level |
| **Event Profile Grouping** | Groups events into categories (Premium, Potential, At-Risk) with a 3D interactive visualisation |
| **Booking Demand Forecast** | Predicts future reservations using historical data |
| **Revenue Outlook** | Financial forecast for the coming months |
| **Client Feedback Tone** | Analyses whether client feedback is positive, negative, or neutral |
| **Personalised Event Suggestions** | Recommends events a client would enjoy |
| **Unusual Activity Alert** | Flags events with abnormal financial data |
| **Advanced Loyalty Predictor** | Second-opinion loyalty analysis |

### Key Frontend Features

- **Angular 20** with signals and zoneless change detection
- **Three.js** 3D visualisation for clustering results
- **Chart.js** inline charts in the AI chatbot
- **Lightweight Charts** for forecast time-series
- **GSAP** scroll animations
- **Ng-Zorro Ant Design** UI components
- **Power BI** embedded dashboards
- **Dark/light theme** toggle

---

## Backend — API Endpoints

### FastAPI (port 8000)

| Endpoint | Method | Description |
|---|---|---|
| `/predict/price` | POST | Price prediction |
| `/predict/fidelisation` | POST | Client return likelihood |
| `/predict/loyalty` | POST | Quick loyalty check |
| `/forecast` | POST | Booking demand forecast |
| `/predict/sentiment` | POST | Feedback tone analysis |
| `/recommendations` | POST | Personalised event suggestions |
| `/detect/anomalies` | GET | Unusual activity detection |
| `/predict/dl` | POST | Advanced loyalty predictor |
| `/revenue/forecast` | GET | Revenue outlook |
| `/lab/train/*` | POST | Train individual models |
| `/alerts` | GET | Pipeline alerts |

### Flask (port 5000)

| Endpoint | Method | Description |
|---|---|---|
| `/predict-cluster` | POST | Event profile grouping (KMeans / DBSCAN) |
| `/train-models` | POST | Train clustering models |

---

## Automation — n8n Workflows

Five workflow files are included:

| File | Pipeline |
|---|---|
| `n8n_workflow_price_prediction.json` | Scheduled price model training + prediction |
| `n8n_workflow_loyalty_prediction.json` | Loyalty scoring with CSV export + email campaigns |
| `n8n_workflow_kmeans_clustering.json` | KMeans clustering with Google Sheets export |
| `n8n_workflow_dbscan_clustering.json` | DBSCAN clustering with Google Sheets export |
| `n8n_workflow_unified_pipeline.json` | **Single merged workflow** running all 4 pipelines in parallel |

Import any workflow into n8n at `http://localhost:5678`.

---

## Monitoring

- **Prometheus** (`http://localhost:9090`) — metrics collection
- **Grafana** (`http://localhost:3000`, admin/admin) — dashboards
- **MLflow** (`http://localhost:5001`) — experiment tracking

---

## Authentication

Built-in role-based access:

| Email | Role | Tools Available |
|---|---|---|
| `marketing@gmail.com` | Marketing Team | Loyalty, Sentiment, Recommendations, Advanced |
| `quality@gmail.com` | Quality Team | Return Likelihood, Sentiment, Anomalies |
| `operationel@gmail.com` | Operations Team | Forecast, Grouping, Anomalies |
| `business@gmail.com` | Business Team | Pricing, Revenue, Advanced |
| `karimmakni14@gmail.com` | Administrator | All tools |

**Password:** `12345678`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Angular 20, TypeScript, SCSS |
| Backend | Python, FastAPI, Flask |
| ML / AI | scikit-learn, XGBoost, Prophet, LSTM, MLP |
| Visualisation | Three.js, Chart.js, Lightweight Charts, Power BI |
| Database | PostgreSQL 16 |
| Automation | n8n |
| Orchestration | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana, MLflow |
| Chatbot | Groq LLaMA |

---

## License

Project developed at **Esprit** for the **PABI 4ERP BI6** programme (2025–2026).
