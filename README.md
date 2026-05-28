# EventZilla BI

**End-to-end event management BI platform** — star-schema data warehouse, 10 production ML models, AI chatbot, full observability, and 11-microservice Docker deployment.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Angular 20 Dashboard                    │
│  (Marketing · Quality · Operations · Business profiles)   │
└──────────────┬───────────────────────────┬────────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│   FastAPI Backend     │   │   Power BI Deep-dive         │
│   + AI Chatbot        │   │   Analytics                  │
│   (Groq LLaMA 3.3)    │   └──────────────────────────────┘
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│                   Data Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ Talend   │  │ Airflow  │  │ PostgreSQL            │   │
│  │ ETL      │─▶│ Pipeline │─▶│ Star-Schema DW        │   │
│  └──────────┘  │ Orchest. │  │ (15 dims, 12 meas.)  │   │
│                └──────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│                ML Layer (MLflow)                          │
│  ┌──────┐ ┌──────┐ ┌───────┐ ┌──────┐ ┌───────┐        │
│  │RF    │ │SARIMA│ │Prophet│ │LGBM  │ │K-Means│ ...      │
│  └──────┘ └──────┘ └───────┘ └──────┘ └───────┘        │
│  Pricing · Forecasting · Churn · Anomaly · Segmentation  │
└──────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│               Observability Stack                         │
│  Prometheus ──▶ Grafana (4 dashboards, 5 alert rules)    │
│  n8n ──▶ Automated ML retraining (5 workflows)           │
│  Docker Compose ──▶ 11 microservices                     │
│  nginx ──▶ Cloudflare Tunnel                             │
└──────────────────────────────────────────────────────────┘
```

## Features

- **Data Warehouse**: Star-schema (15 dimensions, 12 measures), ETL pipelines via Talend + Airflow, processing event, reservation, beneficiary, and marketing data
- **10 ML Models**: Random Forest, SARIMA, Prophet, LightGBM, Holt-Winters, MLP, K-Means, DBSCAN — for pricing, demand forecasting, churn prediction, anomaly detection, customer segmentation
- **MLOps**: MLflow tracking, model registry, automated comparison
- **Dashboard**: Angular 20 with 4 role-based profiles + Power BI integration
- **AI Chatbot**: Groq LLaMA 3.3-70b — natural language to SQL, auto-renders charts (handles ~80% of analytical queries)
- **Observability**: Prometheus + Grafana (ML Pipeline Health, API Performance, Business KPIs, System Health) with custom PromQL alerts
- **Infrastructure**: 11 Docker Compose microservices, multi-stage builds, nginx reverse proxy, Cloudflare Tunnel

## Setup

```bash
# Clone the repository
git clone https://github.com/adriansalvadorekomo/Esprit-PABI-4ERPBI6-2526-EventZella.git
cd Esprit-PABI-4ERPBI6-2526-EventZella

# Start all services
docker compose up -d

# Access the dashboard
open http://localhost:4200
```

## Tech Stack

| Category | Technologies |
|---|---|
| Frontend | Angular 20, TypeScript |
| Backend | FastAPI, Python |
| Database | PostgreSQL (star-schema DW) |
| ETL/Orchestration | Talend, Airflow |
| ML | Scikit-learn, PyTorch, MLflow |
| Monitoring | Prometheus, Grafana |
| Automation | n8n |
| Infrastructure | Docker Compose, nginx, Cloudflare Tunnel |
