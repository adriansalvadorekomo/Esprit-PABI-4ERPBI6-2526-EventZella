# EventZella BI – Business Intelligence Platform

## Overview

This project was developed as part of the **PIDEV – 4th ERPBI6 Year Engineering Program** at **Esprit School of Engineering** (Academic Year 2025–2026).

EventZella BI is a **Business Intelligence platform** that transforms operational data from the EventZella system into strategic, data-driven insights.

EventZella, developed by Teckcatalyze, is an event management solution that allows users to:

- Manage events using an intelligent budgeting system  
- Explore, compare, and book service providers  

Although the operational system manages transactions efficiently, its data was not being fully leveraged for analytics and decision-making. This BI platform introduces a structured analytical layer — from ETL to interactive dashboards and ML-powered predictions — to extract business value from that data.

---

## Features

### BI & Analytics
- Interactive analytical dashboards (Power BI embedded)
- User behavior analysis (budgets, preferences, event types)
- Provider performance tracking (reservations, ratings, complaints)
- Market trend analysis
- Real-time KPI monitoring

### ETL & Data Warehousing
- **Talend** jobs for staging, dimensional, and star-schema population
- Structured data warehouse with fact and dimension tables
- Historical data persistence for trend analysis

### Automation & Orchestration
- **Apache Airflow** DAGs to schedule Talend job execution
- **n8n** workflows for ML pipeline automation and alerting
- End-to-end automated ETL → ML → Dashboard pipeline

### Machine Learning & Decision Tools
- **10 decision tools** for non-technical stakeholders:

| Tool | What it does |
|---|---|
| **Smart Event Pricing** | Estimates the best price for your event |
| **Client Return Likelihood** | Predicts whether a client will come back |
| **Client Loyalty Check** | Quick yes/no on client loyalty |
| **Event Profile Grouping** | Groups events into categories (3D visualisation) |
| **Booking Demand Forecast** | Predicts future reservations |
| **Revenue Outlook** | Financial forecast for coming months |
| **Client Feedback Tone** | Analyses feedback sentiment |
| **Personalised Event Suggestions** | Recommends events to clients |
| **Unusual Activity Alert** | Flags abnormal financial data |
| **Advanced Loyalty Predictor** | Second-opinion loyalty analysis |

### Monitoring
- Prometheus metrics collection
- Grafana operational dashboards
- MLflow experiment tracking

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Angular 20, TypeScript, SCSS, Ng-Zorro Ant Design |
| **Data Visualisation** | Power BI, Three.js, Chart.js, Lightweight Charts |
| **Backend API** | Python — FastAPI (port 8000), Flask (port 5000) |
| **ML / AI** | scikit-learn, XGBoost, Prophet, LSTM, MLP Classifier |
| **Database** | PostgreSQL 16 (Data Warehouse) |
| **ETL** | Talend Open Studio (Data Integration) |
| **Orchestration** | Apache Airflow, n8n |
| **Containerisation** | Docker, Docker Compose |
| **Monitoring** | Prometheus, Grafana, MLflow |
| **Chatbot** | Groq LLaMA (via API) |

---

## Architecture

### Data Flow

```
Raw CSV Files (operational data)
        ↓
   Talend (ETL)
        ↓
PostgreSQL (Data Warehouse)
        ↓
 FastAPI / Flask API
        ↓
  Angular Dashboard
```

The system separates transactional processing from analytical processing to ensure:

- Clean data modeling
- Performance optimisation
- Scalable reporting
- Strategic insight generation

### Full Architecture Diagram

```
┌──────────┐     ┌───────────┐     ┌──────────┐
│  Angular  │────▶│  FastAPI  │────▶│ Postgres │
│  Frontend │     │  (port 8000)    │   (DW)   │
│  (port 4200)    ├───────────┤     └──────────┘
│           │     │  Flask    │          ▲
│           │     │  (port 5000)         │
│           │     ├───────────┤    ┌─────┴──────┐
│           │     │  MLflow   │    │   Talend   │
│           │     │  (port 5001)   │   (ETL)    │
│           │     └───────────┘    └─────┬──────┘
│           │          ▲                 │
└───────────┘          │          Apache Airflow
                 ┌─────┴──────┐    (Scheduling)
                 │  n8n       │
                 │ (port 5678)│
                 └────────────┘
```

---

## Talend — ETL Jobs

The ETL layer is built with **Talend Open Studio** and consists of two master jobs:

### `job_master_dw` — Data Warehouse Population
Extracts raw operational data from CSV files, transforms it, and loads it into the PostgreSQL data warehouse. Sub-jobs include:

| Job | Description |
|---|---|
| `dim_date` | Date dimension |
| `dim_events` | Event dimension |
| `dim_reservation` | Reservation dimension |
| `dim_locations` | Location dimension |
| `dim_complaints` | Complaint dimension |
| `dim_competitors` | Competitor dimension |
| `dim_reviews` | Review dimension |
| `category_dw` | Category dimension |
| `benficiary_dwh` | Beneficiary dimension |

> **Run scripts:** `job_master_dw_run.bat` (Windows), `job_master_dw_run.sh` (Linux/Mac)

### `job_master_sa` — Star Schema Automation
Transforms the data warehouse into star schemas for analytical consumption. Sub-jobs:

| Job | Description |
|---|---|
| `SAbeneficiary` | Beneficiary star schema |
| `SAevent` | Event star schema |
| `SAreservation` | Reservation star schema |
| `SAprovider` | Provider star schema |
| `SAcategory` | Category star schema |
| `SAsubcategory` | Subcategory star schema |
| `SAservice` | Service star schema |
| `SAcomplaint` | Complaint star schema |
| `SAevaluation` | Evaluation star schema |
| `SAlocation` | Location star schema |
| `SAvisitors` | Visitor star schema |
| `SAreviews` | Review star schema |
| `SAmarketing` | Marketing star schema |
| `SAcompetitor` | Competitor star schema |
| `SAsaison` | Season star schema |
| `SAcategory_service` | Category-service bridge |

Both jobs and their metadata are located in:
- `jobs/job_master_dw_0.1/` — DW job artifacts
- `jobs/job_master_sa_0.1/` — SA job artifacts
- `dags/AUTOMATIZATION/` — Talend project files

---

## Apache Airflow — DAG Scheduling

Apache Airflow orchestrates the execution of Talend jobs on a scheduled cadence. The DAGs are located in the `dags/` directory and handle:

- Triggering `job_master_dw` for daily warehouse refreshes
- Triggering `job_master_sa` for star-schema updates
- Monitoring job completion and failure alerts

This ensures fresh analytical data is always available for the dashboards and ML models.

---

## n8n — ML Pipeline Automation

Five **n8n workflow** files automate the ML lifecycle:

| File | Pipeline |
|---|---|
| `n8n_workflow_price_prediction.json` | Scheduled price model training → inference → DB storage |
| `n8n_workflow_loyalty_prediction.json` | Loyalty scoring with CSV export + email campaigns |
| `n8n_workflow_kmeans_clustering.json` | KMeans clustering with Google Sheets export |
| `n8n_workflow_dbscan_clustering.json` | DBSCAN clustering with Google Sheets export |
| `n8n_workflow_unified_pipeline.json` | **Single merged workflow** — runs all 4 pipelines in parallel |

Import any workflow into n8n at `http://localhost:5678`.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)
- Python 3.11+ (for local backend dev)
- Talend Open Studio (for ETL modifications)
- Apache Airflow (for job scheduling)

### Environment Setup

```bash
cp backend/.env.example backend/.env
```

Key environment variables:

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

Starts all services: postgres, fastapi, flask, frontend, n8n, prometheus, and grafana.

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
├── backend/                    # FastAPI + Flask ML backend
│   ├── api/                    # FastAPI routes and models
│   ├── eventzilla_api/         # SQL queries and business logic
│   ├── models/                 # Trained ML models (.pkl, .joblib)
│   ├── app.py / app2.py        # Flask entry points
│   ├── main.py                 # Alternative backend entry point
│   ├── train*.py               # Training scripts
│   └── requirements.txt
│
├── eventzilla-front/           # Angular 20 frontend
│   └── src/app/
│       ├── components/         # Header, footer, chatbot, charts
│       ├── pages/home/         # Main dashboard page
│       ├── services/           # API, auth, theme services
│       └── models/             # TypeScript interfaces
│
├── dags/
│   └── AUTOMATIZATION/         # Talend project + Airflow scheduling
│       ├── process/SA/         # Star Schema Talend jobs
│       └── metadata/           # Connection metadata
│
├── jobs/
│   ├── job_master_dw_0.1/      # Data Warehouse Talend job
│   └── job_master_sa_0.1/      # Star Schema Talend job
│
├── data/                       # Data files
├── docker/                     # Docker config files (Prometheus, n8n)
├── models/                     # Additional model artifacts
├── scripts/                    # Utility scripts
├── eda/                        # Exploratory data analysis notebooks
├── forecasting/                # Time-series forecasting scripts
│
├── n8n_workflow_*.json         # n8n workflow exports
├── docker-compose.yml          # Full stack orchestration
├── backend.Dockerfile          # Backend image
└── frontend.Dockerfile         # Frontend image (Nginx)
```

---

## API Endpoints

### FastAPI (port 8000) — ML Predictions

| Endpoint | Method | Description |
|---|---|---|
| `/predict/price` | POST | Price estimation |
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

### Flask (port 5000) — Clustering

| Endpoint | Method | Description |
|---|---|---|
| `/predict-cluster` | POST | Event profile grouping |
| `/train-models` | POST | Train clustering models |

---

## Authentication

Built-in role-based access:

| Email | Role | Tools Available |
|---|---|---|
| `marketing@gmail.com` | Marketing | Loyalty, Sentiment, Recommendations, Advanced |
| `quality@gmail.com` | Quality | Return Likelihood, Sentiment, Anomalies |
| `operationel@gmail.com` | Operations | Forecast, Grouping, Anomalies |
| `business@gmail.com` | Business | Pricing, Revenue, Advanced |
| `karimmakni14@gmail.com` | Admin | All tools |

**Password:** `12345678`

---

## Monitoring & Observability

| Service | URL | Credentials |
|---|---|---|
| Prometheus | `http://localhost:9090` | — |
| Grafana | `http://localhost:3000` | admin / admin |
| MLflow | `http://localhost:5001` | — |
| n8n | `http://localhost:5678` | admin / admin |

---

## Contributors

- Walid Fehry  
- Emna Trabelsi  
- Hejer Mnejja  
- Karim Makni  
- Amir Jabeur  
- Adrian Salvador Ekomo Mesi Obono  

4th ERPBI6 Year Engineering Students  
Esprit School of Engineering – Tunisia  

---

## Academic Context

Developed at **Esprit School of Engineering – Tunisia**  
**PIDEV – 4ERPBI6** | Academic Year 2025–2026  

This project focuses on **Business Intelligence**, **Data Engineering**, and **Enterprise Analytics Systems**.

---

## Repository Topics

`esprit-school-of-engineering` `academic-project` `esprit-pidev` `2025-2026`  
`business-intelligence` `angular` `flask` `postgresql` `talend` `apache-airflow` `n8n` `threejs` `machine-learning`

---

## Acknowledgments

We thank **Teckcatalyze** and the academic staff of **Esprit School of Engineering** for their guidance and support.
