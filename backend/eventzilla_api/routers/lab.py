from functools import lru_cache

from fastapi import APIRouter, Query

from ..schemas.ml import InputFidelisation
from ..services import MLService


router = APIRouter()


@lru_cache(maxsize=1)
def get_service() -> MLService:
    return MLService()


@router.post("/recommend/events")
def recommend_events(
    beneficiary_id: int = Query(..., ge=1),
    n_reco: int = Query(default=5, ge=1, le=10),
):
    return get_service().recommend_events(beneficiary_id=beneficiary_id, n_reco=n_reco)


@router.post("/predict/anomalies")
def detect_anomalies():
    return get_service().detect_anomalies()


@router.post("/predict/deep-learning")
def predict_deep_learning(data: InputFidelisation):
    return get_service().predict_deep_learning(data)


@router.post("/train/sarima")
def train_sarima():
    return get_service().train_sarima()


@router.post("/train/prophet")
def train_prophet():
    return get_service().train_prophet()


@router.post("/train/lstm")
def train_lstm():
    return get_service().train_lstm()


@router.post("/train/loyalty")
def train_loyalty():
    return get_service().train_loyalty()


@router.post("/train/price")
def train_price():
    return get_service().train_price()


@router.post("/train/compare")
def compare_models():
    return get_service().compare_models()
