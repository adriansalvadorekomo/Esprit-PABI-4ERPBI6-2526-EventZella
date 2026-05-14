import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd
import numpy as np
import pickle, os, datetime, warnings
import psycopg2, mlflow
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ��� MLflow �������������������������������������
mlflow.set_tracking_uri("file:./mlruns")
mlflow.set_experiment("prophet_final_price_forecast")
# Note: MLflow Prophet autolog may not be available in all versions
# mlflow.prophet.autolog(disable=True)  # This line caused an error

# ��� DB �����������������������������������������
from settings import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
query = """
SELECT e.event_date, f.final_price
FROM fact_suivi_event f
LEFT JOIN dim_event e ON f.event_sk = e.event_sk
WHERE e.event_date IS NOT NULL
"""
df = pd.read_sql(query, conn)
conn.close()

df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
df = df.dropna(subset=["event_date"])

# Prophet requires columns named 'ds' and 'y'
prophet_df = df[["event_date", "final_price"]].rename(
    columns={"event_date": "ds", "final_price": "y"}
)
prophet_df = prophet_df.dropna()

print(f"Data points: {len(prophet_df)} from {prophet_df['ds'].min()} to {prophet_df['ds'].max()}")

# ��� Train / test split �������������������������
n_test = 3
train = prophet_df.iloc[:-n_test]
test = prophet_df.iloc[-n_test:]

# ��� Initialize and fit Prophet model �������������
model = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=False,
    daily_seasonality=False,
    seasonality_mode='additive'
)
model.fit(train)

# ��� Make future dataframe and predict �����������
future = model.make_future_dataframe(periods=n_test, freq='MS')
forecast = model.predict(future)

# ��� Extract forecast for test period �������������
forecast_test = forecast.iloc[-n_test:][["ds", "yhat", "yhat_lower", "yhat_upper"]]
forecast_values = forecast_test["yhat"].values
actual_values = test["y"].values

# ��� Calculate metrics ����������������������������
mae = mean_absolute_error(actual_values, forecast_values)
rmse = np.sqrt(mean_squared_error(actual_values, forecast_values))
mape = np.mean(np.abs((actual_values - forecast_values) / np.maximum(np.abs(actual_values), 1))) * 100

print(f"\n?? Test metrics (original scale):")
print(f"   MAE  = {mae:,.2f}")
print(f"   RMSE = {rmse:,.2f}")
print(f"   MAPE = {mape:.2f}%")

# ��� Forecast future (6 months) �������������������
horizon = 6
future_future = model.make_future_dataframe(periods=horizon, freq='MS')
forecast_future = model.predict(future_future)
forecast_future_values = forecast_future.iloc[-horizon:][["ds", "yhat", "yhat_lower", "yhat_upper"]]
forecast_future_values = forecast_future_values.rename(columns={"ds": "date", "yhat": "value", "yhat_lower": "lower_bound", "yhat_upper": "upper_bound"})

# ��� Save forecast ��������������������������������
forecast_path = "models/prophet_forecast.csv"
forecast_future_values[["date", "value"]].to_csv(forecast_path, index=False)
print(f"\nForecast next {horizon} months:")
print(forecast_future_values[["date", "value"]].to_string(index=False))

# ��� MLflow logging ��������������������������������
version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
mlflow.end_run()
with mlflow.start_run():
    mlflow.log_params({
        "yearly_seasonality": True,
        "weekly_seasonality": False,
        "daily_seasonality": False,
        "seasonality_mode": "additive",
        "n_test_months": n_test,
        "forecast_horizon": horizon,
    })
    mlflow.log_metrics({
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
    })
    
    # Log the model
    # mlflow.prophet.log_model(model, "model")  # This might also cause issues
    # Instead, we'll save it manually and log as artifact
    
    # Create and log forecast plot
    fig = model.plot(forecast)
    plt.title("Prophet Forecast")
    plot_path = f"models/prophet_forecast_plot_{version}.png"
    plt.savefig(plot_path)
    plt.close()
    mlflow.log_artifact(plot_path, artifact_path="plots")
    
    # Save model locally
    with open(f"models/prophet_model_{version}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open("prophet_model.pkl", "wb") as f:
        pickle.dump(model, f)

print(f"\n? Prophet training done - version: {version}")