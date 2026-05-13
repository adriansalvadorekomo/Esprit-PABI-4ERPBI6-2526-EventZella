from flask import Flask, request, jsonify
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.neighbors import NearestNeighbors
from train import run_clustering_pipeline, run_loyalty_classification, get_engine
import threading
import time
import sys
import mlflow
import json

# --- IMPORT MONITORING ---
from prometheus_client import Gauge, Counter, Summary, CONTENT_TYPE_LATEST, REGISTRY, generate_latest

app = Flask(__name__)

# ============================================================
# CONFIGURATION MONITORING
# ============================================================
print("🚀 [DEBUG] Démarrage du système de monitoring...", file=sys.stderr)

@app.route("/whoami")
def whoami():
    return "THIS IS MY APP"

@app.route('/metrics')
def metrics():
    """Expose toutes les métriques du registre par défaut."""
    return generate_latest(REGISTRY), 200, {'Content-Type': CONTENT_TYPE_LATEST}

MODEL_CONFIDENCE = Gauge(
    'model_loyalty_confidence',
    'Score de confiance du modèle RF'
)

PREDICTION_COUNT = Counter(
    'model_predictions_total',
    'Nombre total de prédictions',
    ['endpoint', 'algo']
)

LATENCY_SUMMARY = Summary(
    'model_prediction_latency_seconds',
    'Temps de réponse du modèle'
)

DATA_MISSING_VALUES = Counter(
    'cluster_input_missing_values_total',
    'Nombre de valeurs manquantes dans les inputs clustering'
)

DATA_FRESHNESS_SECONDS = Gauge(
    'cluster_data_freshness_seconds',
    'Âge des données reçues'
)

DATA_COMPLETENESS = Gauge(
    'cluster_data_completeness_ratio',
    'Ratio de complétude des données (0-1)'
)

OUT_OF_RANGE_VALUES = Counter(
    'cluster_out_of_range_values_total',
    'Valeurs hors plage normale'
)

# Métriques de performance Clustering
CLUSTER_SILHOUETTE_KMEANS = Gauge(
    "cluster_silhouette_score_kmeans",
    "Silhouette score du clustering KMeans"# <--- AJOUTE CECI
)

CLUSTER_SILHOUETTE_DBSCAN = Gauge(
    "cluster_silhouette_score_dbscan",
    "Silhouette score du clustering DBSCAN"
)

CLUSTER_DB = Gauge(
    "cluster_davies_bouldin_score",
    "Davies Bouldin score"
)

CLUSTER_N = Gauge(
    "cluster_n_clusters",
    "Nombre de clusters détectés" # <--- AJOUTE CECI
)


CLUSTER_ERRORS = Counter(
    'cluster_errors_total',
    'Nombre total d erreurs clustering',
    ['algo']
)

def load_cluster_metrics():
    try:
        with open("cluster_metrics.json", "r") as f:
            m = json.load(f)

        # On aligne sur les vraies clés de ton JSON
        val_km_sil = m.get("kmeans_silhouette", 0)
        val_km_db = m.get("kmeans_davies_bouldin", 0)
        val_db_n = m.get("dbscan_n_clusters", 0)
        
        # On met à jour les Gauges
        CLUSTER_SILHOUETTE_KMEANS.set(val_km_sil)
        CLUSTER_DB.set(val_km_db)
        CLUSTER_N.set(val_db_n)
        
        # Note: 'dbscan_silhouette' n'est pas dans ton JSON, 
        # donc on le laisse à 0 ou on le supprime
        CLUSTER_SILHOUETTE_DBSCAN.set(m.get("dbscan_silhouette", 0))

        print(f"✅ Métriques mises à jour : Silhouette={val_km_sil}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Erreur lors du chargement du JSON: {e}", file=sys.stderr)


def init_metrics():
    print("📊 [DEBUG] Initialisation des labels Prometheus...", file=sys.stderr)
    try:
        PREDICTION_COUNT.labels(endpoint='/predict-loyalty', algo='random_forest').inc(0)
        PREDICTION_COUNT.labels(endpoint='/predict-cluster', algo='kmeans').inc(0)
        PREDICTION_COUNT.labels(endpoint='/predict-cluster', algo='dbscan').inc(0)
        CLUSTER_SILHOUETTE_KMEANS.set(0)
        CLUSTER_SILHOUETTE_DBSCAN.set(0)
        CLUSTER_DB.set(0)
        CLUSTER_N.set(0)



        print("✅ [DEBUG] Labels initialisés.", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ [DEBUG] Erreur init metrics: {e}", file=sys.stderr)



def count_missing(item):
    return sum(
        1 for v in item.values()
        if v is None or v == "" or v == "null"
    )


# ============================================================
# CHARGEMENT MODELES
# ============================================================
kmeans = None
dbscan = None
rf_loyalty = None
scaler = None
pca = None
freq_map = None
cluster_names = None

try:
    kmeans = joblib.load('kmeans_model.joblib')
    dbscan = joblib.load('dbscan_model.joblib')
    rf_loyalty = joblib.load('loyalty_model.joblib')
    scaler = joblib.load('scaler.joblib')
    pca = joblib.load('pca.joblib')

    try:
        freq_map = joblib.load('freq_map.joblib')
    except:
        freq_map = {}

    try:
        cluster_names = joblib.load('cluster_names.joblib')
    except:
        cluster_names = {0: "Client Premium", 1: "Client Potentiel", 2: "Client à Risque", -1: "Inclassable"}

    print("✅ [DEBUG] Modèles chargés", file=sys.stderr)
    init_metrics()

except Exception as e:
    print(f"❌ [DEBUG] Erreur chargement: {e}", file=sys.stderr)

@app.route('/debug-metrics')
def debug_metrics():
    print(PREDICTION_COUNT.collect(), file=sys.stderr)
    return "ok"

# ============================================================
def get_season(month):
    if month in [12, 1, 2]: return 'hiver'
    elif month in [3, 4, 5]: return 'printemps'
    elif month in [6, 7, 8]: return 'ete'
    else: return 'automne'


# ============================================================
# LOYALTY ROUTE
# ============================================================
@app.route('/predict-loyalty', methods=['POST'])
@LATENCY_SUMMARY.time()
def predict_loyalty():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON vide'}), 400

        price = float(data.get('price', 0))
        budget = float(data.get('budget', 0))
        event_date = pd.to_datetime(data.get('event_date', datetime.now()))
        month = event_date.month

        season_map = {'hiver': 0, 'printemps': 1, 'ete': 2, 'automne': 3}
        type_map = {'Corporate Event': 0, 'Private Party': 1, 'Wedding': 2, 'inconnu': 3}

        processed = {
            'price': price,
            'budget': budget,
            'final_price': float(data.get('final_price', 0)),
            'rating': float(data.get('rating', 0)),
            'visitors': float(data.get('visitors', 0)),
            'price_budget_ratio': price / (budget + 0.01),
            'has_complaint': 1 if data.get('id_complaint') else 0,
            'type_encoded': type_map.get(data.get('event_type'), 3),
            'season_encoded': season_map.get(get_season(month), 0),
            'is_weekend': 1 if event_date.dayofweek >= 5 else 0,
            'month': month
        }

        df = pd.DataFrame([processed])
        cols = ['price','budget','final_price','rating','visitors',
                'price_budget_ratio','has_complaint','type_encoded',
                'season_encoded','is_weekend','month']

        prediction = rf_loyalty.predict(df[cols])
        prob = rf_loyalty.predict_proba(df[cols])[:, 1]

        # metrics
        MODEL_CONFIDENCE.set(prob[0])
        PREDICTION_COUNT.labels(endpoint='/predict-loyalty', algo='random_forest').inc()

        return jsonify({
            'is_loyal': int(prediction[0]),
            'probability': round(float(prob[0]), 2),
            'status': 'success'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route("/model-health", methods=["GET"])
def model_health():
    try:
        with open("cluster_metrics.json", "r") as f:
            m = json.load(f)

        return jsonify({
            "status": "success",
            "kmeans_silhouette": m.get("kmeans_silhouette"),
            "dbscan_silhouette": m.get("dbscan_silhouette"),
            "kmeans_davies_bouldin": m.get("kmeans_davies_bouldin"),
            "dbscan_n_clusters": m.get("dbscan_n_clusters")
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ============================================================
# CLUSTER ROUTE
# ============================================================
@app.route('/predict-cluster', methods=['POST'])
@LATENCY_SUMMARY.time()
def predict_cluster():
    algo = 'unknown'

    try:
        data_in = request.get_json()

        # ============================================================
        # REQUEST VALIDATION + TRACKING
        # ============================================================
        if not data_in:
            CLUSTER_REQUESTS.labels(algo='unknown').inc()
            CLUSTER_ERRORS.labels(algo='unknown').inc()
            return jsonify({'error': 'JSON vide'}), 400

        algo = data_in.get('algo', 'dbscan').lower()
        CLUSTER_REQUESTS.labels(algo=algo).inc()

        # ============================================================
        # DATA QUALITY METRICS (inchangé)
        # ============================================================
        missing = count_missing(data_in)
        DATA_MISSING_VALUES.inc(missing)

        total_fields = len(data_in) if isinstance(data_in, dict) else 1
        DATA_COMPLETENESS.set(1 - (missing / total_fields))

        items = [data_in] if isinstance(data_in, dict) else data_in

        processed = []
        for item in items:
            subject = item.get('complaint_subject', 'Autre')
            subject_freq = freq_map.get(subject, 0.0)

            processed.append({
                'budget': float(item.get('budget', 0)),
                'price': float(item.get('price', 0)),
                'final_price': float(item.get('final_price', 0)),
                'rating': float(item.get('rating', 0)),
                'visitors': float(item.get('visitors', 0)),
                'complaint_status_bin': 1 if item.get('complaint_status') == 'open' else 0,
                'complaint_subject_freq': subject_freq,
                'event_type_Corporate Event': 1 if item.get('event_type') == 'Corporate Event' else 0,
                'event_type_Private Party': 1 if item.get('event_type') == 'Private Party' else 0,
                'event_type_Wedding': 1 if item.get('event_type') == 'Wedding' else 0,
                'reservation_status_cancelled': 1 if item.get('reservation_status') == 'cancelled' else 0,
                'reservation_status_confirmed': 1 if item.get('reservation_status') == 'confirmed' else 0,
                'reservation_status_pending': 1 if item.get('reservation_status') == 'pending' else 0
            })

        cols = [
            'budget','price','final_price','rating','visitors',
            'complaint_status_bin','complaint_subject_freq',
            'event_type_Corporate Event','event_type_Private Party',
            'event_type_Wedding','reservation_status_cancelled',
            'reservation_status_confirmed','reservation_status_pending'
        ]

        df = pd.DataFrame(processed)[cols]

        # ============================================================
        # MODEL INFERENCE
        # ============================================================
        X = scaler.transform(df)
        X = pca.transform(X)

        if algo == 'dbscan':
            samples = dbscan.components_
            labels = dbscan.labels_[dbscan.core_sample_indices_]

            nn = NearestNeighbors(n_neighbors=10).fit(samples)
            _, idx = nn.kneighbors(X)

            cluster_ids = [int(labels[i[0]]) for i in idx]

        else:
            cluster_ids = kmeans.predict(X).tolist()

        # ============================================================
        # SUCCESS METRICS (STABILITY PART)
        # ============================================================
        CLUSTER_SUCCESS.labels(algo=algo).inc(len(cluster_ids))

        return jsonify({
            'clusters': cluster_ids,
            'algo': algo,
            'status': 'success'
        })

    except Exception as e:
        # ============================================================
        # ERROR METRICS (STABILITY CORE)
        # ============================================================
        CLUSTER_ERRORS.labels(algo=algo).inc()

        return jsonify({
            'error': str(e),
            'status': 'failed'
        }), 500

# ============================================================
@app.route('/train-models', methods=['POST'])
def train_models():
    def train():
        engine = get_engine()
        # On suppose que run_clustering_pipeline met à jour le fichier cluster_metrics.json
        km, db, sc, pc, _ = run_clustering_pipeline(engine)
        rf, _ = run_loyalty_classification(engine)
        
        joblib.dump(km, 'kmeans_model.joblib')
        joblib.dump(db, 'dbscan_model.joblib')
        joblib.dump(rf, 'loyalty_model.joblib')
        joblib.dump(sc, 'scaler.joblib')
        joblib.dump(pc, 'pca.joblib')

        global kmeans, dbscan, rf_loyalty, scaler, pca
        kmeans, dbscan, rf_loyalty, scaler, pca = km, db, rf, sc, pc
        
        # Recharger les métriques dans Prometheus après entraînement
        load_cluster_metrics()

    threading.Thread(target=train).start()
    return jsonify({'status': 'started'}), 202

# ============================================================
if __name__ == '__main__':
    load_cluster_metrics()
    print(generate_latest(REGISTRY).decode())
    print("🔥 CODE VERSION VS CODE ACTIF 🔥")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)