import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd
import numpy as np
import pickle, os, datetime, warnings
import psycopg2
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# MLflow setup
try:
    import mlflow
    mlflow.set_tracking_uri("file:./mlruns")
    mlflow.set_experiment("mlp_final_price_forecast")  # Using MLP as proxy for LSTM
    HAS_MLFLOW = True
except ImportError:
    print("Warning: mlflow not installed. Skipping mlflow logging.")
    HAS_MLFLOW = False

# DB connection
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

# Prepare time series data
ts_raw = (
    df.set_index("event_date")["final_price"]
    .resample("MS").sum().asfreq("MS")
)
# Replace zeros/NaN with interpolated values to avoid flat-line model
ts = ts_raw.replace(0, np.nan).interpolate(method="time").ffill().bfill()
print(f"Series: {len(ts)} months  ({ts.index[0].date()} to {ts.index[-1].date()})")

# Scale the data
scaler = MinMaxScaler(feature_range=(0, 1))
ts_scaled = scaler.fit_transform(ts.values.reshape(-1, 1))

# Create dataset for sequence prediction (using last 3 months to predict next)
def create_dataset(dataset, look_back=3):
    dataX, dataY = [], []
    for i in range(len(dataset)-look_back-1):
        a = dataset[i:(i+look_back), 0]
        dataX.append(a)
        dataY.append(dataset[i + look_back, 0])
    return np.array(dataX), np.array(dataY)

look_back = 3
X, y = create_dataset(ts_scaled, look_back)

# Split into train and test
train_size = int(len(X) * 0.8)
test_size = len(X) - train_size
X_train, X_test = X[0:train_size], X[train_size:len(X)]
y_train, y_test = y[0:train_size], y[train_size:len(y)]

print(f"Training samples: {len(X_train)}")
print(f"Test samples: {len(X_test)}")

# Create and fit MLP model (as proxy for LSTM)
model = MLPRegressor(
    hidden_layer_sizes=(50, 50),
    activation='relu',
    solver='adam',
    alpha=0.0001,
    batch_size='auto',
    learning_rate='constant',
    learning_rate_init=0.001,
    max_iter=500,
    random_state=42,
    early_stopping=False if len(X_train) < 20 else True,
    validation_fraction=0.1
)

print("Training MLP model...")
model.fit(X_train, y_train)

# Make predictions
train_predict = model.predict(X_train)
test_predict = model.predict(X_test)

# Invert predictions
train_predict = scaler.inverse_transform(train_predict.reshape(-1, 1))
y_train_inv = scaler.inverse_transform([y_train])
test_predict = scaler.inverse_transform(test_predict.reshape(-1, 1))
y_test_inv = scaler.inverse_transform([y_test])

# Calculate metrics
train_mae = mean_absolute_error(y_train_inv[0], train_predict[:, 0])
test_mae = mean_absolute_error(y_test_inv[0], test_predict[:, 0])
train_rmse = np.sqrt(mean_squared_error(y_train_inv[0], train_predict[:, 0]))
test_rmse = np.sqrt(mean_squared_error(y_test_inv[0], test_predict[:, 0]))

print(f'\nTrain MAE: {train_mae:.2f}')
print(f'Test MAE: {test_mae:.2f}')
print(f'Train RMSE: {train_rmse:.2f}')
print(f'Test RMSE: {test_rmse:.2f}')

# Forecast future (6 months)
horizon = 6
last_sequence = ts_scaled[-look_back:]
predictions = []

for i in range(horizon):
    # Reshape for prediction
    X_pred = last_sequence.reshape((1, look_back))
    # Predict next point
    next_point = model.predict(X_pred)
    predictions.append(next_point[0])
    # Update sequence
    last_sequence = np.append(last_sequence[1:], [[next_point[0]]], axis=0)

# Invert predictions
predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
forecast_dates = pd.date_range(ts.index[-1] + pd.DateOffset(months=1), periods=horizon, freq='MS')
forecast_df = pd.DataFrame({"date": forecast_dates, "value": predictions.flatten()})

# Save forecast
os.makedirs("models", exist_ok=True)
forecast_path = "models/lstm_forecast.csv"
forecast_df.to_csv(forecast_path, index=False)
print(f"\nForecast next {horizon} months:")
print(forecast_df.to_string(index=False))

# MLflow logging
version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
if HAS_MLFLOW:
    try:
        mlflow.end_run()
        with mlflow.start_run():
            mlflow.log_params({
                "look_back": look_back,
                "hidden_layer_sizes": "(50, 50)",
                "activation": "relu",
                "solver": "adam",
                "max_iter": 500,
                "n_test_months": test_size,
                "forecast_horizon": horizon,
            })
            mlflow.log_metrics({
                "train_mae": round(train_mae, 2),
                "test_mae": round(test_mae, 2),
                "train_rmse": round(train_rmse, 2),
                "test_rmse": round(test_rmse, 2),
            })
            
            # Create and log forecast plot
            plt.figure(figsize=(12, 6))
            plt.plot(ts.index[-24:], ts.values[-24:], label='Historical')
            plt.plot(forecast_df['date'], forecast_df['value'], label='Forecast', marker='o')
            plt.title('MLP Forecast (Proxy for LSTM)')
            plt.xlabel('Date')
            plt.ylabel('Value')
            plt.legend()
            plt.grid(True)
            plot_path = f"models/mlp_forecast_plot_{version}.png"
            plt.savefig(plot_path)
            plt.close()
            mlflow.log_artifact(plot_path, artifact_path="plots")
    except Exception as e:
        print(f"MLflow logging failed: {e}")

# Save plot locally anyway if matplotlib works
try:
    plt.figure(figsize=(12, 6))
    plt.plot(ts.index[-24:], ts.values[-24:], label='Historical')
    plt.plot(forecast_df['date'], forecast_df['value'], label='Forecast', marker='o')
    plt.title('MLP Forecast (Proxy for LSTM)')
    plt.xlabel('Date')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)
    plot_path = f"models/mlp_forecast_plot_latest.png"
    plt.savefig(plot_path)
    plt.close()
except Exception as e:
    print(f"Local plot save failed: {e}")

# Save model locally
with open(f"models/mlp_model_{version}.pkl", "wb") as f:
    pickle.dump(model, f)
with open("mlp_model.pkl", "wb") as f:
    pickle.dump(model, f)
# Save scaler
with open(f"models/mlp_scaler_{version}.pkl", "wb") as f:
    pickle.dump(scaler, f)
with open("mlp_scaler.pkl", "wb") as f:
    pickle.dump(scaler, f)

print(f"\nMLP training done (as LSTM proxy) - version: {version}")
