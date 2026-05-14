#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# EventZilla — Health Verification Script
# Run this to check if everything is working after the observability + MLflow setup.
# ═══════════════════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
  local name=$1
  local cmd=$2
  echo -n "  [ ] $name ... "
  if eval "$cmd" > /dev/null 2>&1; then
    echo -e "${GREEN}PASS${NC}"
    ((PASS++))
  else
    echo -e "${RED}FAIL${NC}"
    ((FAIL++))
  fi
}

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        EventZilla — System Verification                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── 1. DOCKER SERVICES ────────────────────────────────────────────────
echo "━━━ 1. Docker Services ───────────────────────────────────────────"

check "PostgreSQL is running"   "docker exec eventzilla-postgres pg_isready -U postgres"
check "FastAPI is running"      "curl -s http://localhost:8000/health | grep -q ok"
check "Flask is running"        "curl -s http://localhost:5000/ | grep -q EventZilla"
check "Frontend is serving"     "curl -s -o /dev/null -w '%{http_code}' http://localhost:4200 | grep -q 200"
check "n8n is running"          "curl -s -o /dev/null -w '%{http_code}' http://localhost:5678 | grep -q 200"
check "Prometheus is running"   "curl -s http://localhost:9090/-/ready | grep -q Prometheus"
check "Grafana is running"      "curl -s http://localhost:3000/api/health | grep -q ok"

# ─── 2. PROMETHEUS SCRAPING ────────────────────────────────────────────
echo ""
echo "━━━ 2. Prometheus Targets ────────────────────────────────────────"

check "FastAPI is UP in Prometheus" "curl -s http://localhost:9090/api/v1/targets | grep -q 'fastapi.*\"health\":\"up\"'"
check "Flask is UP in Prometheus"   "curl -s http://localhost:9090/api/v1/targets | grep -q 'flask.*\"health\":\"up\"'"

# ─── 3. API ENDPOINTS ─────────────────────────────────────────────────
echo ""
echo "━━━ 3. API Endpoints ─────────────────────────────────────────────"

check "GET /health returns ok"              "curl -s http://localhost:8000/health | grep -q ok"
check "GET /categories returns data"        "curl -s http://localhost:8000/categories | grep -q '\['"
check "GET /alerts/unread-count"            "curl -s http://localhost:8000/alerts/unread-count | grep -q unread_count"
check "POST /predict/price works"           "curl -s -X POST http://localhost:8000/predict/price -H 'Content-Type: application/json' -d '{\"price\":500,\"budget\":2000,\"marketing_spend\":300,\"new_beneficiaries\":50,\"reservations\":80,\"nb_events\":5,\"avg_spent_user\":120,\"type\":\"Corporate Event\",\"status\":\"confirmed\"}' | grep -q prediction"

# ─── 4. FASTAPI METRICS (Prometheus endpoint) ──────────────────────────
echo ""
echo "━━━ 4. Prometheus Metrics Endpoints ──────────────────────────────"

check "FastAPI /metrics is exposed"   "curl -s http://localhost:8000/metrics | grep -q http_requests_total"
check "Flask /metrics is exposed"     "curl -s http://localhost:5000/metrics | grep -q flask_http_request_total"

# ─── 5. MLflow ────────────────────────────────────────────────────────
echo ""
echo "━━━ 5. MLflow ────────────────────────────────────────────────────"

check "MLflow UI is running"          "curl -s http://localhost:5001 | grep -q mlflow"
check "MLflow experiments exist"      "curl -s http://localhost:5001/api/2.0/mlflow/experiments/list | grep -q rf_final_price"

# ─── 6. GRAFANA ────────────────────────────────────────────────────────
echo ""
echo "━━━ 6. Grafana ───────────────────────────────────────────────────"

check "Grafana datasources provisioned" "curl -s http://admin:admin@localhost:3000/api/datasources | grep -q Prometheus"
check "Grafana dashboards provisioned"  "curl -s http://admin:admin@localhost:3000/api/search | grep -q 'ML Pipeline Health'"

# ─── 7. POSTGRESQL ────────────────────────────────────────────────────
echo ""
echo "━━━ 7. Database ──────────────────────────────────────────────────"

check "DW_event database exists"      "docker exec eventzilla-postgres psql -U postgres -d DW_event -c 'SELECT 1' | grep -q '1 row'"
check "fact_suivi_event has data"     "docker exec eventzilla-postgres psql -U postgres -d DW_event -c 'SELECT COUNT(*) FROM fact_suivi_event' | grep -q '[1-9]'"
check "n8n_alerts table exists"       "docker exec eventzilla-postgres psql -U postgres -d DW_event -c 'SELECT to_regclass('\''n8n_alerts'\'')' | grep -q n8n_alerts"

# ─── RESULTS ──────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Results: $PASS passed, $FAIL failed"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}Everything looks good!${NC}"
  echo ""
  echo "Open these in your browser:"
  echo "  Frontend:      http://localhost:4200"
  echo "  FastAPI docs:  http://localhost:8000/docs"
  echo "  Prometheus:    http://localhost:9090"
  echo "  Grafana:       http://localhost:3000 (admin/admin)"
  echo "  MLflow:        http://localhost:5001"
  echo "  n8n:           http://localhost:5678 (admin/admin)"
else
  echo -e "${RED}Some checks failed. Check docker-compose logs for details:${NC}"
  echo "  docker-compose logs fastapi --tail=50"
  echo "  docker-compose logs prometheus --tail=20"
  echo "  docker-compose logs grafana --tail=20"
fi
