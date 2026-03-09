import os
import sys
import pandas as pd
import numpy as np
import sqlite3
sys.path.append('/workspaces/DerivativesApp/smartoptions')
from smartoptions_config.settings import DB_PATH

def load_price_data(instrument="NIFTY"):
    """Load historical price data from database into a DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close FROM price_data WHERE instrument=? ORDER BY date ASC",
        conn, params=(instrument,)
    )
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    print(f"Loaded {len(df)} rows of {instrument} data")
    return df

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_adx(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    return dx.rolling(window=period).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    macd_line = calculate_ema(series, fast) - calculate_ema(series, slow)
    signal_line = calculate_ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line

def calculate_all_signals(instrument="NIFTY"):
    """Calculate all technical indicators and signal scores."""
    print(f"\n=== Calculating signals for {instrument} ===")
    df = load_price_data(instrument)

    # EMAs
    df["ema_9"]  = calculate_ema(df["close"], 9)
    df["ema_21"] = calculate_ema(df["close"], 21)
    df["ema_50"] = calculate_ema(df["close"], 50)

    # EMA crossover direction
    df["ema_cross"] = 0
    df.loc[df["ema_9"] > df["ema_21"], "ema_cross"] = 1
    df.loc[df["ema_9"] < df["ema_21"], "ema_cross"] = -1

    # Days since last crossover
    cross_change = df["ema_cross"].diff().ne(0)
    df["days_since_cross"] = cross_change.cumsum()
    df["days_since_cross"] = df.groupby("days_since_cross").cumcount()

    # Price vs 50 EMA
    df["spot_vs_50ema_pct"] = ((df["close"] - df["ema_50"]) / df["ema_50"]) * 100

    # Momentum
    df["rsi"] = calculate_rsi(df["close"], 14)
    df["macd"], df["macd_signal"], df["macd_hist"] = calculate_macd(df["close"])
    df["adx"] = calculate_adx(df, 14)
    df["price_range_5d"] = ((df["high"].rolling(5).max() - df["low"].rolling(5).min()) / df["close"]) * 100

    # Score each day
    df["signal_score"] = 0
    df["direction"] = "NEUTRAL"

    for idx in df.index:
        row = df.loc[idx]
        score = 0

        if row["ema_cross"] == 1:
            direction = "BULLISH"
        elif row["ema_cross"] == -1:
            direction = "BEARISH"
        else:
            continue

        # EMA cross freshness (25 pts)
        days = row["days_since_cross"]
        score += 25 if days <= 2 else 15 if days <= 5 else 5

        # RSI (20 pts)
        rsi = row["rsi"]
        if direction == "BULLISH":
            score += 20 if rsi < 35 else 10 if rsi < 45 else 5
        else:
            score += 20 if rsi > 65 else 10 if rsi > 55 else 5

        # ADX (10 pts)
        score += 10 if row["adx"] > 30 else 5 if row["adx"] > 20 else 0

        # MACD confirmation (10 pts)
        if direction == "BULLISH" and row["macd_hist"] > 0: score += 10
        elif direction == "BEARISH" and row["macd_hist"] < 0: score += 10

        # Price vs 50 EMA (10 pts)
        pct = row["spot_vs_50ema_pct"]
        if direction == "BULLISH" and pct > 1.5: score += 10
        elif direction == "BEARISH" and pct < -1.5: score += 10
        elif abs(pct) > 0.5: score += 5

        df.loc[idx, "signal_score"] = score
        df.loc[idx, "direction"] = direction

    df = df.dropna(subset=["rsi", "adx", "macd"])

    print(f"Signals calculated for {len(df)} trading days")
    print(f"Bullish days:  {len(df[df['direction']=='BULLISH'])}")
    print(f"Bearish days:  {len(df[df['direction']=='BEARISH'])}")
    print(f"Neutral days:  {len(df[df['direction']=='NEUTRAL'])}")
    print(f"High score days (>=65): {len(df[df['signal_score']>=65])}")
    return df

def get_latest_signal(instrument="NIFTY"):
    """Get today's signal and print a clear summary."""
    df = calculate_all_signals(instrument)
    latest = df.iloc[-1]

    print(f"\n=== Latest Signal for {instrument} ===")
    print(f"Date:          {latest.name.strftime('%d %b %Y')}")
    print(f"Close:         {latest['close']:.1f}")
    print(f"Direction:     {latest['direction']}")
    print(f"Signal Score:  {latest['signal_score']}/100")
    print(f"RSI:           {latest['rsi']:.1f}")
    print(f"ADX:           {latest['adx']:.1f}")
    print(f"MACD Hist:     {latest['macd_hist']:.2f}")
    print(f"vs 50-EMA:     {latest['spot_vs_50ema_pct']:.2f}%")

    if latest["signal_score"] >= 65:
        print(f"\n*** QUALIFYING SIGNAL FOUND ***")
        print(f"*** Score: {latest['signal_score']}/100 | Direction: {latest['direction']} ***")
    else:
        print(f"\nNo qualifying signal today (score {latest['signal_score']} < 65 threshold)")

    return latest

if __name__ == "__main__":
    get_latest_signal("NIFTY")
