"""
MediVend Predictive Analytics Model
=====================================
Drug demand forecasting using Linear Regression with seasonal features.
Designed as a drop-in replacement for Prophet when offline.

Usage:
    python medivend_forecast_model.py

Outputs:
    - forecast_results.json    (for dashboard / API)
    - forecast_results.csv     (for review)
    - synthetic_sales.csv      (generated training data)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

# Use current working directory for output files
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
np.random.seed(42)
FORECAST_DAYS = 30
TODAY = datetime.today()

# Drugs derived from your disease-drug dataset (SFDA matched)
DRUGS = [
    {"name": "Multivitamins Syrup",        "trade": "Junior Syrup w/ Royal Jelly",  "category": "Supplement"},
    {"name": "Urea 10% Cream",             "trade": "Eucerin Urea Repair",           "category": "Dermatology"},
    {"name": "FreeStyle Libre Reader",     "trade": "FreeStyle Libre 2 Reader",      "category": "Diabetes Device"},
    {"name": "FreeStyle Libre Sensor",     "trade": "FreeStyle Libre 2 Sensor",      "category": "Diabetes Device"},
    {"name": "Activated Charcoal Powder",  "trade": "VitaThrive Charcoal",           "category": "Gastro"},
    {"name": "Calamine Lotion 8%",         "trade": "Calarose Lotion",               "category": "Dermatology"},
    {"name": "BD Insulin Pen Needle 4mm",  "trade": "BD Microfine Pen Needle",       "category": "Diabetes"},
    {"name": "Desloratadine 5mg",          "trade": "Deslin 5mg Film-coated",        "category": "Allergy"},
    {"name": "Zinc Oxide 15% Cream",       "trade": "Diaper Rash Cream Plus",        "category": "Dermatology"},
    {"name": "Diosmin 500mg",              "trade": "Capillo Film-coated",           "category": "Vascular"},
    {"name": "Perampanel 2mg",             "trade": "Fycompa 2mg",                   "category": "Neurology"},
    {"name": "Accu-Chek Test Strips",      "trade": "Accu-Chek Instant Strips",      "category": "Diabetes"},
    {"name": "Panadol 500mg",              "trade": "Panadol Extra",                 "category": "Analgesic"},
    {"name": "Amoxicillin 500mg",          "trade": "Amoxil 500mg Capsules",         "category": "Antibiotic"},
    {"name": "Ibuprofen 400mg",            "trade": "Brufen 400mg",                  "category": "Analgesic"},
]

# Simulated current inventory (units)
INVENTORY = {
    "Multivitamins Syrup":        145,
    "Urea 10% Cream":             88,
    "FreeStyle Libre Reader":     22,
    "FreeStyle Libre Sensor":     55,
    "Activated Charcoal Powder":  67,
    "Calamine Lotion 8%":         102,
    "BD Insulin Pen Needle 4mm":  210,
    "Desloratadine 5mg":          134,
    "Zinc Oxide 15% Cream":       79,
    "Diosmin 500mg":              43,
    "Perampanel 2mg":             18,
    "Accu-Chek Test Strips":      95,
    "Panadol 500mg":              312,
    "Amoxicillin 500mg":          56,
    "Ibuprofen 400mg":            178,
}

# Seasonal demand multipliers by drug category (month -> multiplier)
SEASONAL_PROFILE = {
    "Analgesic":       {12:1.4, 1:1.4, 2:1.3, 3:1.1, 6:1.0, 7:0.9, 11:1.2},
    "Antibiotic":      {1:1.3,  2:1.3, 3:1.2, 9:1.1, 10:1.2, 11:1.3, 12:1.4},
    "Allergy":         {3:1.5,  4:1.6, 5:1.4, 6:1.2, 9:1.3},
    "Dermatology":     {6:1.3,  7:1.4, 8:1.3, 12:0.8},
    "Diabetes":        {},  # year-round
    "Diabetes Device": {},
    "Supplement":      {9:1.2, 10:1.1, 11:1.2, 12:1.3, 1:1.2},
    "Gastro":          {1:1.2, 7:1.1, 8:1.1},
    "Neurology":       {},
    "Vascular":        {},
}

BASE_DEMAND = {
    "Multivitamins Syrup":        22,
    "Urea 10% Cream":             14,
    "FreeStyle Libre Reader":      4,
    "FreeStyle Libre Sensor":     12,
    "Activated Charcoal Powder":   9,
    "Calamine Lotion 8%":         11,
    "BD Insulin Pen Needle 4mm":  28,
    "Desloratadine 5mg":          19,
    "Zinc Oxide 15% Cream":       13,
    "Diosmin 500mg":              10,
    "Perampanel 2mg":              5,
    "Accu-Chek Test Strips":      21,
    "Panadol 500mg":              38,
    "Amoxicillin 500mg":          17,
    "Ibuprofen 400mg":            29,
}


# ─────────────────────────────────────────────
# STEP 1: GENERATE SYNTHETIC SALES DATA
# ─────────────────────────────────────────────
def generate_sales_data(days_back=730):
    start = TODAY - timedelta(days=days_back)
    dates = pd.date_range(start=start, end=TODAY - timedelta(days=1), freq='D')
    records = []

    for drug_info in DRUGS:
        drug = drug_info["name"]
        category = drug_info["category"]
        base = BASE_DEMAND[drug]
        seasonal = SEASONAL_PROFILE.get(category, {})

        for date in dates:
            multiplier = seasonal.get(date.month, 1.0)
            trend = 1 + (date.dayofyear / 365) * 0.05  # slight upward trend
            noise = np.random.normal(0, base * 0.15)
            qty = max(0, int(base * multiplier * trend + noise))

            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "drug_name": drug,
                "category": category,
                "quantity_sold": qty,
                "day_of_week": date.dayofweek,
                "month": date.month,
                "is_weekend": int(date.dayofweek >= 5),
            })

    df = pd.DataFrame(records)
    df.to_csv(os.path.join(OUTPUT_DIR, "synthetic_sales.csv"), index=False)
    print(f"✅ Generated {len(df):,} sales records for {len(DRUGS)} drugs")
    return df


# ─────────────────────────────────────────────
# STEP 2: FEATURE ENGINEERING
# ─────────────────────────────────────────────
def build_features(drug_df):
    drug_df = drug_df.copy()
    drug_df["date"] = pd.to_datetime(drug_df["date"])
    drug_df = drug_df.sort_values("date")

    drug_df["day_of_year"] = drug_df["date"].dt.dayofyear
    drug_df["week_of_year"] = drug_df["date"].dt.isocalendar().week.astype(int)
    drug_df["month"] = drug_df["date"].dt.month
    drug_df["day_of_week"] = drug_df["date"].dt.dayofweek
    drug_df["is_weekend"] = (drug_df["day_of_week"] >= 5).astype(int)
    drug_df["t"] = (drug_df["date"] - drug_df["date"].min()).dt.days

    # Fourier features for seasonality (annual cycle)
    drug_df["sin_annual"] = np.sin(2 * np.pi * drug_df["day_of_year"] / 365)
    drug_df["cos_annual"] = np.cos(2 * np.pi * drug_df["day_of_year"] / 365)
    drug_df["sin_monthly"] = np.sin(2 * np.pi * drug_df["month"] / 12)
    drug_df["cos_monthly"] = np.cos(2 * np.pi * drug_df["month"] / 12)

    return drug_df


# ─────────────────────────────────────────────
# STEP 3: TRAIN + FORECAST PER DRUG
# ─────────────────────────────────────────────
FEATURE_COLS = ["t", "day_of_week", "is_weekend", "month",
                "sin_annual", "cos_annual", "sin_monthly", "cos_monthly"]

def train_and_forecast(drug_df, drug_name):
    df = build_features(drug_df)
    X = df[FEATURE_COLS].values
    y = df["quantity_sold"].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    # Build future dataframe
    future_dates = pd.date_range(start=TODAY, periods=FORECAST_DAYS, freq='D')
    t_max = df["t"].max()
    future_df = pd.DataFrame({"date": future_dates})
    future_df["t"] = t_max + (future_df["date"] - future_dates[0]).dt.days + 1
    future_df["day_of_week"] = future_df["date"].dt.dayofweek
    future_df["is_weekend"] = (future_df["day_of_week"] >= 5).astype(int)
    future_df["month"] = future_df["date"].dt.month
    future_df["day_of_year"] = future_df["date"].dt.dayofyear
    future_df["sin_annual"] = np.sin(2 * np.pi * future_df["day_of_year"] / 365)
    future_df["cos_annual"] = np.cos(2 * np.pi * future_df["day_of_year"] / 365)
    future_df["sin_monthly"] = np.sin(2 * np.pi * future_df["month"] / 12)
    future_df["cos_monthly"] = np.cos(2 * np.pi * future_df["month"] / 12)

    X_future = scaler.transform(future_df[FEATURE_COLS].values)
    preds = model.predict(X_future)
    preds = np.maximum(preds, 0)

    # Model accuracy on training data
    train_preds = model.predict(X_scaled)
    mae = np.mean(np.abs(train_preds - y))
    rmse = np.sqrt(np.mean((train_preds - y) ** 2))

    # 7-day rolling average from recent actuals
    recent_avg = df["quantity_sold"].tail(30).mean()

    return {
        "forecast": preds.tolist(),
        "forecast_dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "avg_daily_forecast": float(np.mean(preds)),
        "recent_7d_avg": float(df["quantity_sold"].tail(7).mean()),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(model.score(X_scaled, y), 3),
    }


# ─────────────────────────────────────────────
# STEP 4: GENERATE ALERTS
# ─────────────────────────────────────────────
def classify_alert(days_remaining):
    if days_remaining < 5:
        return "CRITICAL"
    elif days_remaining < 10:
        return "WARNING"
    elif days_remaining < 20:
        return "LOW"
    else:
        return "OK"


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def run_pipeline():
    print("=" * 55)
    print("  MediVend Predictive Analytics Pipeline")
    print("=" * 55)

    df_sales = generate_sales_data(days_back=730)

    results = []
    print("\n📊 Training models and generating forecasts...\n")

    for drug_info in DRUGS:
        drug = drug_info["name"]
        category = drug_info["category"]

        drug_df = df_sales[df_sales["drug_name"] == drug].copy()
        forecast_result = train_and_forecast(drug_df, drug)

        avg_daily = forecast_result["avg_daily_forecast"]
        current_stock = INVENTORY[drug]
        days_remaining = current_stock / avg_daily if avg_daily > 0 else 999
        stockout_date = (TODAY + timedelta(days=days_remaining)).strftime("%Y-%m-%d")
        alert = classify_alert(days_remaining)

        result = {
            "drug_id": DRUGS.index(drug_info) + 1,
            "drug_name": drug,
            "trade_name": drug_info["trade"],
            "category": drug_info["category"],
            "current_stock": current_stock,
            "predicted_daily_usage": round(avg_daily, 1),
            "days_remaining": round(days_remaining, 1),
            "stock_out_date": stockout_date,
            "alert_level": alert,
            "model_mae": forecast_result["mae"],
            "model_r2": forecast_result["r2"],
            "forecast_30d": [round(v, 1) for v in forecast_result["forecast"]],
            "forecast_dates": forecast_result["forecast_dates"],
        }

        results.append(result)

        icon = {"CRITICAL": "🔴", "WARNING": "🟠", "LOW": "🟡", "OK": "🟢"}[alert]
        print(f"  {icon} {drug:<35} | Stock: {current_stock:>4} | ~{avg_daily:.1f}/day | {days_remaining:.0f} days left | {alert}")

    # Save outputs
    with open(os.path.join(OUTPUT_DIR, "forecast_results.json"), "w") as f:
        json.dump(results, f, indent=2)

    # Summary CSV
    summary_cols = ["drug_id", "drug_name", "trade_name", "category",
                    "current_stock", "predicted_daily_usage",
                    "days_remaining", "stock_out_date", "alert_level",
                    "model_mae", "model_r2"]
    df_results = pd.DataFrame(results)[summary_cols]
    df_results.to_csv(os.path.join(OUTPUT_DIR, "forecast_results.csv"), index=False)

    # Print summary
    print("\n" + "=" * 55)
    print("  ALERTS SUMMARY")
    print("=" * 55)
    critical = [r for r in results if r["alert_level"] == "CRITICAL"]
    warning  = [r for r in results if r["alert_level"] == "WARNING"]
    low      = [r for r in results if r["alert_level"] == "LOW"]

    if critical:
        print(f"\n🔴 CRITICAL ({len(critical)} drugs - order immediately!):")
        for r in critical:
            print(f"   → {r['drug_name']} will run out in {r['days_remaining']:.0f} days ({r['stock_out_date']})")
    if warning:
        print(f"\n🟠 WARNING ({len(warning)} drugs - order soon):")
        for r in warning:
            print(f"   → {r['drug_name']} — {r['days_remaining']:.0f} days remaining")
    if low:
        print(f"\n🟡 LOW ({len(low)} drugs - monitor):")
        for r in low:
            print(f"   → {r['drug_name']} — {r['days_remaining']:.0f} days remaining")

    print(f"\n✅ Results saved to forecast_results.json and forecast_results.csv")
    print(f"   Total drugs tracked: {len(results)}")
    print(f"   Forecast horizon: {FORECAST_DAYS} days\n")

    return results

if __name__ == "__main__":
    results = run_pipeline()
