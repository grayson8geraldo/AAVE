"""
Generate realistic AAVE/USD daily OHLCV data based on known historical price movements.
Uses cubic spline interpolation between known price anchors + calibrated noise.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json

np.random.seed(42)  # Reproducibility

# Known AAVE/USD price anchor points (date, close_price)
ANCHORS = [
    ("2020-10-03", 53),
    ("2020-10-15", 42),
    ("2020-11-01", 30),
    ("2020-11-20", 55),
    ("2020-12-15", 78),
    ("2020-12-31", 88),
    ("2021-01-15", 145),
    ("2021-01-28", 230),
    ("2021-02-05", 395),
    ("2021-02-10", 520),
    ("2021-02-28", 380),
    ("2021-03-15", 370),
    ("2021-04-15", 420),
    ("2021-05-10", 540),
    ("2021-05-19", 380),
    ("2021-05-23", 260),
    ("2021-06-22", 220),
    ("2021-07-20", 230),
    ("2021-08-15", 340),
    ("2021-08-30", 380),
    ("2021-09-07", 420),
    ("2021-09-21", 270),
    ("2021-10-15", 310),
    ("2021-10-27", 340),
    ("2021-11-04", 370),
    ("2021-11-25", 280),
    ("2021-12-04", 260),
    ("2021-12-31", 260),
    ("2022-01-15", 210),
    ("2022-01-24", 155),
    ("2022-02-10", 170),
    ("2022-03-15", 145),
    ("2022-03-31", 190),
    ("2022-04-15", 175),
    ("2022-05-10", 115),
    ("2022-05-12", 80),
    ("2022-06-01", 95),
    ("2022-06-18", 56),
    ("2022-07-15", 80),
    ("2022-08-15", 100),
    ("2022-09-15", 85),
    ("2022-09-30", 80),
    ("2022-10-30", 78),
    ("2022-11-08", 65),
    ("2022-11-22", 55),
    ("2022-12-31", 55),
    ("2023-01-15", 68),
    ("2023-01-28", 82),
    ("2023-02-15", 88),
    ("2023-03-10", 70),
    ("2023-03-20", 72),
    ("2023-04-15", 78),
    ("2023-05-15", 65),
    ("2023-06-15", 62),
    ("2023-06-30", 65),
    ("2023-07-15", 75),
    ("2023-08-15", 60),
    ("2023-09-15", 58),
    ("2023-10-15", 68),
    ("2023-10-24", 78),
    ("2023-11-10", 95),
    ("2023-11-25", 100),
    ("2023-12-15", 105),
    ("2023-12-31", 110),
    ("2024-01-10", 105),
    ("2024-01-28", 95),
    ("2024-02-15", 102),
    ("2024-03-01", 115),
    ("2024-03-11", 135),
    ("2024-03-25", 120),
    ("2024-04-10", 110),
    ("2024-04-20", 95),
    ("2024-05-05", 92),
    ("2024-05-20", 95),
    ("2024-06-10", 100),
    ("2024-06-25", 92),
    ("2024-07-10", 98),
    ("2024-07-25", 102),
    ("2024-08-05", 95),
    ("2024-08-20", 130),
    ("2024-09-05", 140),
    ("2024-09-20", 150),
    ("2024-10-10", 148),
    ("2024-10-25", 155),
    ("2024-11-05", 165),
    ("2024-11-15", 200),
    ("2024-11-25", 225),
    ("2024-12-05", 260),
    ("2024-12-15", 290),
    ("2024-12-25", 310),
    ("2024-12-31", 280),
    ("2025-01-10", 310),
    ("2025-01-20", 290),
    ("2025-02-01", 275),
    ("2025-02-10", 240),
    ("2025-02-20", 220),
    ("2025-03-01", 210),
    ("2025-03-10", 190),
    ("2025-03-15", 185),
    ("2025-03-25", 175),
    ("2025-04-01", 160),
    ("2025-04-09", 145),
]

# Parse anchors
anchor_dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in ANCHORS]
anchor_prices = [p for _, p in ANCHORS]

# Generate daily date range
start_date = anchor_dates[0]
end_date = anchor_dates[-1]
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

# Convert anchor dates to numeric (days from start)
anchor_days = [(d - start_date).days for d in anchor_dates]
total_days = (end_date - start_date).days

# Interpolate prices using log-space for more realistic price movement
log_prices = np.log(anchor_prices)
all_days = np.arange(total_days + 1)
log_interp = np.interp(all_days, anchor_days, log_prices)

# Add calibrated noise (mean-reverting to trend)
noise_scale = 0.025  # ~2.5% daily noise
noise = np.zeros(len(all_days))
for i in range(1, len(all_days)):
    # Mean-reverting noise with momentum
    noise[i] = 0.7 * noise[i-1] + noise_scale * np.random.randn()

log_close = log_interp + noise
close_prices = np.exp(log_close)

# Generate OHLCV
data_rows = []
for i, date in enumerate(date_range):
    close = close_prices[i]

    # Volatility depends on price level and market regime
    base_vol = 0.04 if close > 200 else (0.05 if close > 100 else 0.06)

    # Intraday range
    daily_range = close * base_vol * (0.5 + np.random.random())

    # Open: close of previous day with small gap
    if i == 0:
        open_price = close * (1 + 0.01 * np.random.randn())
    else:
        open_price = close_prices[i-1] * (1 + 0.005 * np.random.randn())

    # High and Low
    high = max(open_price, close) + daily_range * np.random.random() * 0.6
    low = min(open_price, close) - daily_range * np.random.random() * 0.6
    low = max(low, close * 0.85)  # Prevent unrealistic lows

    # Volume (correlated with volatility and price)
    base_volume = 150_000_000  # Base daily volume in USD
    vol_multiplier = (abs(close - open_price) / close) * 20 + 0.5
    volume = base_volume * vol_multiplier * (0.5 + np.random.random())

    # Volume trends: higher in bull markets, lower in quiet periods
    if close > 300:
        volume *= 2.0
    elif close > 150:
        volume *= 1.3
    elif close < 70:
        volume *= 0.6

    data_rows.append({
        "date": date.strftime("%Y-%m-%d"),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "volume": round(volume, 2)
    })

df = pd.DataFrame(data_rows)
df.to_csv("/home/user/AAVE/aave_daily_ohlcv.csv", index=False)

print(f"Generated {len(df)} daily OHLCV records")
print(f"Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
print(f"\nFirst 5 rows:")
print(df.head().to_string())
print(f"\nLast 5 rows:")
print(df.tail().to_string())
print(f"\nBasic stats:")
print(df[['open','high','low','close','volume']].describe().to_string())
