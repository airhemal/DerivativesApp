import os
import sys
import sqlite3
from datetime import datetime
sys.path.append('/workspaces/DerivativesApp/smartoptions')
from smartoptions_config.settings import DB_PATH
from signals.calculator import calculate_all_signals

# Regime definitions matching our spec exactly
REGIMES = {
    "TRENDING_BULL":  "Strong uptrend. Full scan active. Prefer Call options.",
    "TRENDING_BEAR":  "Strong downtrend. Full scan active. Prefer Put options.",
    "SIDEWAYS":       "Choppy market. Restrict to 1 position. Score threshold raised to 75.",
    "HIGH_VOL":       "Elevated volatility. Half position size. ATM strikes only.",
    "CRISIS":         "Dangerous conditions. NO new trades. Monitor only."
}

def classify_regime(adx, vix, ema_cross, spot_vs_50ema_pct, vix_change_pct=0):
    """
    Classify market regime based on available indicators.
    In Phase 1 we use ADX and EMA since VIX needs separate download.
    VIX defaults to 15 (normal) until we add live VIX fetching.
    """

    # CRISIS check first — always takes priority
    if vix > 25 or vix_change_pct > 15:
        return "CRISIS"

    # HIGH VOLATILITY
    if vix > 22:
        return "HIGH_VOL"

    # SIDEWAYS — weak trend regardless of direction
    if adx < 20:
        return "SIDEWAYS"

    # TRENDING — strong trend detected
    if adx >= 25:
        if ema_cross == 1 and spot_vs_50ema_pct > 0:
            return "TRENDING_BULL"
        elif ema_cross == -1 and spot_vs_50ema_pct < 0:
            return "TRENDING_BEAR"

    # Moderate trend — direction based
    if ema_cross == 1:
        return "TRENDING_BULL"
    elif ema_cross == -1:
        return "TRENDING_BEAR"

    return "SIDEWAYS"

def get_regime_rules(regime):
    """Return trading rules for the current regime."""
    rules = {
        "TRENDING_BULL": {
            "max_positions": 3,
            "min_score": 65,
            "position_size_pct": 1.0,
            "preferred_direction": "BULLISH",
            "new_trades_allowed": True
        },
        "TRENDING_BEAR": {
            "max_positions": 3,
            "min_score": 65,
            "position_size_pct": 1.0,
            "preferred_direction": "BEARISH",
            "new_trades_allowed": True
        },
        "SIDEWAYS": {
            "max_positions": 1,
            "min_score": 75,
            "position_size_pct": 0.75,
            "preferred_direction": "NEUTRAL",
            "new_trades_allowed": True
        },
        "HIGH_VOL": {
            "max_positions": 1,
            "min_score": 70,
            "position_size_pct": 0.5,
            "preferred_direction": "NEUTRAL",
            "new_trades_allowed": True
        },
        "CRISIS": {
            "max_positions": 0,
            "min_score": 999,
            "position_size_pct": 0.0,
            "preferred_direction": "NONE",
            "new_trades_allowed": False
        }
    }
    return rules.get(regime, rules["SIDEWAYS"])

def save_regime_to_db(date, regime, vix, adx, nifty_close, notes=""):
    """Save today's regime classification to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO market_regime_log
        (date, regime, vix, adx, nifty_close, fii_net, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (date, regime, vix, adx, nifty_close, 0, notes))
    conn.commit()
    conn.close()

def run_morning_regime_check(instrument="NIFTY", vix=None):
    """
    Main function called every morning at 8:45 AM.
    Classifies today's market regime and returns trading rules.
    """
    print(f"\n{'='*55}")
    print(f"  MORNING REGIME CHECK")
    print(f"  {datetime.now().strftime('%A, %d %B %Y | %H:%M IST')}")
    print(f"{'='*55}")

    # Get latest signals
    df = calculate_all_signals(instrument)
    latest = df.iloc[-1]

    adx = latest["adx"]
    ema_cross = latest["ema_cross"]
    spot_vs_50ema_pct = latest["spot_vs_50ema_pct"]
    nifty_close = latest["close"]

    # Use provided VIX or default to 15 (normal) until live VIX is added
    if vix is None:
        vix = 15.0
        vix_note = "(default — live VIX fetch coming in next module)"
    else:
        vix_note = "(live)"

    # Classify regime
    regime = classify_regime(adx, vix, ema_cross, spot_vs_50ema_pct)
    rules = get_regime_rules(regime)

    # Plain English direction
    direction_text = "UP (bullish)" if ema_cross == 1 else "DOWN (bearish)" if ema_cross == -1 else "SIDEWAYS"

    print(f"\n  Nifty Close:     {nifty_close:.1f}")
    print(f"  ADX:             {adx:.1f} ({'Strong trend' if adx > 25 else 'Moderate' if adx > 20 else 'Weak/Choppy'})")
    print(f"  India VIX:       {vix:.1f} {vix_note}")
    print(f"  EMA Direction:   {direction_text}")
    print(f"  vs 50-day EMA:   {spot_vs_50ema_pct:.2f}%")

    print(f"\n{'─'*55}")
    print(f"  TODAY'S REGIME:  {regime}")
    print(f"  {REGIMES[regime]}")
    print(f"{'─'*55}")
    print(f"  New trades allowed:    {'YES' if rules['new_trades_allowed'] else 'NO'}")
    print(f"  Max open positions:    {rules['max_positions']}")
    print(f"  Minimum signal score:  {rules['min_score']}")
    print(f"  Position size:         {rules['position_size_pct']*100:.0f}% of normal")
    print(f"  Preferred direction:   {rules['preferred_direction']}")
    print(f"{'='*55}\n")

    # Save to database
    save_regime_to_db(
        date=latest.name.strftime("%Y-%m-%d"),
        regime=regime,
        vix=vix,
        adx=round(adx, 2),
        nifty_close=round(nifty_close, 1),
        notes=f"EMA cross: {ema_cross}, spot_vs_50ema: {spot_vs_50ema_pct:.2f}%"
    )
    print(f"  Regime saved to database.")

    return regime, rules

if __name__ == "__main__":
    run_morning_regime_check("NIFTY")
