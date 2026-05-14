from eventzilla_api.app import create_app
from eventzilla_api.db import get_engine
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import os

app = create_app()


def train_fidelisation():
    engine = get_engine()
    query = """
        SELECT f.sk_beneficiary, f.price, f.budget, f.final_price,
               f.rating, f.visitors, f.marketing_spend, f.id_complaint,
               e.type, e.event_date
        FROM fact_suivi_event f
        JOIN dim_event e ON f.event_sk = e.event_sk
        WHERE f.price > 0 AND f.budget > 0
    """
    frame = pd.read_sql(query, engine)
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce")
    frame = frame.sort_values(["sk_beneficiary", "event_date"])
    frame["month"] = frame["event_date"].dt.month.fillna(1).astype(int)
    frame["day_of_week"] = frame["event_date"].dt.dayofweek.fillna(0).astype(int)
    frame["is_weekend"] = (frame["day_of_week"] >= 5).astype(int)

    def season_for(m):
        return "hiver" if m in (12, 1, 2) else "printemps" if m in (3, 4, 5) else "ete" if m in (6, 7, 8) else "automne"

    frame["season"] = frame["month"].apply(season_for)
    frame["price_budget_ratio"] = frame["price"] / (frame["budget"] + 0.01)
    frame["margin"] = frame["final_price"] - frame["price"]
    frame["has_complaint"] = (~frame["id_complaint"].isna()).astype(int)

    le_type = LabelEncoder()
    frame["type_encoded"] = le_type.fit_transform(frame["type"].fillna("inconnu"))
    le_season = LabelEncoder()
    frame["season_encoded"] = le_season.fit_transform(frame["season"])

    loyalty_map = {}
    for beneficiary in frame["sk_beneficiary"].dropna().unique():
        bf = frame[frame["sk_beneficiary"] == beneficiary].sort_values("event_date")
        if len(bf) <= 1:
            loyalty_map[int(beneficiary)] = 0
            continue
        first_date = bf["event_date"].iloc[0]
        later = bf[(bf["event_date"] > first_date) & (bf["event_date"] <= first_date + pd.DateOffset(months=6))]
        loyalty_map[int(beneficiary)] = 1 if len(later) >= 1 else 0

    frame["is_loyal"] = frame["sk_beneficiary"].map(loyalty_map)
    first_res = frame.groupby("sk_beneficiary").first().reset_index()
    features = first_res[["price", "budget", "final_price", "rating", "visitors",
                          "marketing_spend", "price_budget_ratio", "margin",
                          "has_complaint", "type_encoded", "season_encoded",
                          "is_weekend", "month"]].fillna(0)
    target = first_res["is_loyal"].fillna(0)

    scaler = StandardScaler()
    x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=0.2, random_state=42, stratify=target if target.nunique() > 1 else None)
    x_train_scaled = scaler.fit_transform(x_train)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(x_train_scaled, y_train)

    artifact_dir = os.getcwd()
    joblib.dump(model, os.path.join(artifact_dir, "lr_model.pkl"))
    joblib.dump(scaler, os.path.join(artifact_dir, "scaler_classif.pkl"))
    joblib.dump(le_type, os.path.join(artifact_dir, "le_type.pkl"))
    joblib.dump(le_season, os.path.join(artifact_dir, "le_season.pkl"))

    from sklearn.metrics import accuracy_score, recall_score, roc_auc_score
    x_test_scaled = scaler.transform(x_test)
    y_pred = model.predict(x_test_scaled)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
    }
    try:
        y_proba = model.predict_proba(x_test_scaled)[:, 1]
        metrics["roc_auc"] = round(float(roc_auc_score(y_test, y_proba)), 4)
    except Exception:
        metrics["roc_auc"] = 0.0
    return {"status": "success", "model": "LogisticRegression", "samples": int(len(features)), **metrics}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app2:app", host="0.0.0.0", port=8000, reload=True)
