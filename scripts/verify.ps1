# ═══════════════════════════════════════════════════════════════════════════
# EventZilla — Health Verification Script (PowerShell)
# Run this to check if everything is working after the observability + MLflow setup.
# ═══════════════════════════════════════════════════════════════════════════

$PASS = 0
$FAIL = 0

function Check($name, $cmd) {
    Write-Host "  [ ] $name ... " -NoNewline
    try {
        $null = Invoke-Expression $cmd
        if ($LASTEXITCODE -eq 0 -or $?) {
            Write-Host "PASS" -ForegroundColor Green
            $script:PASS++
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            $script:FAIL++
        }
    } catch {
        Write-Host "FAIL" -ForegroundColor Red
        $script:FAIL++
    }
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        EventZilla — System Verification                     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── 1. DOCKER SERVICES ────────────────────────────────────────────────
Write-Host "━━━ 1. Docker Services ───────────────────────────────────────────" -ForegroundColor Yellow

Check "PostgreSQL is running"   { docker exec eventzilla-postgres pg_isready -U postgres }
Check "FastAPI is running"      { curl -s http://localhost:8000/health }
Check "Flask is running"        { curl -s http://localhost:5000/ }
Check "Frontend is serving"     { curl -s -o $null -w "%{http_code}" http://localhost:4200 }
Check "n8n is running"          { curl -s -o $null -w "%{http_code}" http://localhost:5678 }
Check "Prometheus is running"   { curl -s http://localhost:9090/-/ready }
Check "Grafana is running"      { curl -s http://localhost:3000/api/health }

# ─── 2. PROMETHEUS SCRAPING ────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 2. Prometheus Targets ────────────────────────────────────────" -ForegroundColor Yellow

Check "FastAPI is UP in Prometheus" { curl -s http://localhost:9090/api/v1/targets | Select-String -Pattern 'fastapi.*"health":"up"' }
Check "Flask is UP in Prometheus"   { curl -s http://localhost:9090/api/v1/targets | Select-String -Pattern 'flask.*"health":"up"' }

# ─── 3. API ENDPOINTS ─────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 3. API Endpoints ─────────────────────────────────────────────" -ForegroundColor Yellow

Check "GET /health"                      { curl -s http://localhost:8000/health }
Check "GET /categories"                  { curl -s http://localhost:8000/categories }
Check "GET /alerts/unread-count"         { curl -s http://localhost:8000/alerts/unread-count }
Check "POST /predict/price"              { curl -s -X POST http://localhost:8000/predict/price -H "Content-Type: application/json" -d '{"price":500,"budget":2000,"marketing_spend":300,"new_beneficiaries":50,"reservations":80,"nb_events":5,"avg_spent_user":120,"type":"Corporate Event","status":"confirmed"}' }

# ─── 4. PROMETHEUS METRICS ─────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 4. Prometheus Metrics Endpoints ──────────────────────────────" -ForegroundColor Yellow

Check "FastAPI /metrics"  { curl -s http://localhost:8000/metrics | Select-String -Pattern "http_requests_total" }
Check "Flask /metrics"    { curl -s http://localhost:5000/metrics | Select-String -Pattern "flask_http_request_total" }

# ─── 5. MLflow ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 5. MLflow ────────────────────────────────────────────────────" -ForegroundColor Yellow

Check "MLflow UI is running"            { curl -s http://localhost:5001 | Select-String -Pattern "mlflow" }
Check "MLflow experiments exist"        { curl -s http://localhost:5001/api/2.0/mlflow/experiments/list | Select-String -Pattern "rf_final_price" }

# ─── 6. GRAFANA ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 6. Grafana ───────────────────────────────────────────────────" -ForegroundColor Yellow

Check "Grafana datasources provisioned" { curl -s http://admin:admin@localhost:3000/api/datasources | Select-String -Pattern "Prometheus" }
Check "Grafana dashboards provisioned"  { curl -s http://admin:admin@localhost:3000/api/search | Select-String -Pattern "ML Pipeline Health" }

# ─── 7. DATABASE ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "━━━ 7. Database ──────────────────────────────────────────────────" -ForegroundColor Yellow

Check "DW_event database exists"        { docker exec eventzilla-postgres psql -U postgres -d DW_event -c "SELECT 1" }
Check "fact_suivi_event has data"       { docker exec eventzilla-postgres psql -U postgres -d DW_event -c "SELECT COUNT(*) FROM fact_suivi_event" }
Check "n8n_alerts table exists"         { docker exec eventzilla-postgres psql -U postgres -d DW_event -c "SELECT to_regclass('n8n_alerts')" }

# ─── RESULTS ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
if ($FAIL -eq 0) {
    Write-Host "║  All $PASS checks passed!                                        ║" -ForegroundColor Green
} else {
    Write-Host "║  $PASS passed, $FAIL failed                                           ║" -ForegroundColor Red
}
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if ($FAIL -eq 0) {
    Write-Host "Everything looks good!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Open these in your browser:"
    Write-Host "  Frontend:      http://localhost:4200"
    Write-Host "  FastAPI docs:  http://localhost:8000/docs"
    Write-Host "  Prometheus:    http://localhost:9090"
    Write-Host "  Grafana:       http://localhost:3000 (admin/admin)"
    Write-Host "  MLflow:        http://localhost:5001"
    Write-Host "  n8n:           http://localhost:5678 (admin/admin)"
} else {
    Write-Host "Some checks failed. Check logs:" -ForegroundColor Red
    Write-Host "  docker-compose logs fastapi --tail=50"
    Write-Host "  docker-compose logs prometheus --tail=20"
    Write-Host "  docker-compose logs grafana --tail=20"
}
