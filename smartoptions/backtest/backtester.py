import os
import sys
import pandas as pd
import numpy as np
import sqlite3
sys.path.append('/workspaces/DerivativesApp/smartoptions')
from smartoptions_config.settings import DB_PATH, STOP_LOSS_PCT, TARGET_PCT, MIN_DAYS_TO_EXPIRY
from signals.calculator import calculate_all_signals

BROKERAGE_PER_ORDER = 20
STT_PCT = 0.0625 / 100
EXCHANGE_CHARGE_PCT = 0.053 / 100
GST_PCT = 0.18
STAMP_DUTY_PCT = 0.003 / 100
NIFTY_LOT_SIZE = 50

def estimate_option_premium(nifty_price, direction, days_to_expiry=30):
    monthly_factor = days_to_expiry / 30
    base_premium_pct = 0.008
    premium = nifty_price * base_premium_pct * monthly_factor
    return round(premium, 1)

def calculate_transaction_costs(premium, lot_size=NIFTY_LOT_SIZE):
    total_premium = premium * lot_size
    stt_buy = total_premium * STT_PCT
    brokerage_buy = BROKERAGE_PER_ORDER
    exchange_buy = total_premium * EXCHANGE_CHARGE_PCT
    stamp_duty = total_premium * STAMP_DUTY_PCT
    gst_buy = (brokerage_buy + exchange_buy) * GST_PCT
    total_buy_cost = stt_buy + brokerage_buy + exchange_buy + stamp_duty + gst_buy
    brokerage_sell = BROKERAGE_PER_ORDER
    exchange_sell = total_premium * EXCHANGE_CHARGE_PCT
    gst_sell = (brokerage_sell + exchange_sell) * GST_PCT
    total_sell_cost = brokerage_sell + exchange_sell + gst_sell
    return round(total_buy_cost + total_sell_cost, 2)

def simulate_trade(df, entry_idx, direction, entry_price, holding_days=21):
    stop_loss_price = entry_price * (1 - STOP_LOSS_PCT / 100)
    target_price = entry_price * (1 + TARGET_PCT / 100)
    positions = df.index.tolist()
    entry_pos = positions.index(entry_idx)
    max_pos = min(entry_pos + holding_days, len(positions) - 1)

    for i in range(entry_pos + 1, max_pos + 1):
        idx = positions[i]
        row = df.loc[idx]
        days_held = i - entry_pos
        price_change_pct = (row["close"] - df.loc[entry_idx, "close"]) / df.loc[entry_idx, "close"]
        if direction == "BULLISH":
            option_pnl_pct = price_change_pct * 50
        else:
            option_pnl_pct = -price_change_pct * 50
        current_option_price = entry_price * (1 + option_pnl_pct / 100)
        if current_option_price <= stop_loss_price:
            return current_option_price, "STOP_LOSS", days_held, -STOP_LOSS_PCT
        if current_option_price >= target_price:
            return current_option_price, "TARGET", days_held, TARGET_PCT

    final_row = df.loc[positions[max_pos]]
    price_change_pct = (final_row["close"] - df.loc[entry_idx, "close"]) / df.loc[entry_idx, "close"]
    if direction == "BULLISH":
        option_pnl_pct = price_change_pct * 50
    else:
        option_pnl_pct = -price_change_pct * 50
    exit_price = max(entry_price * (1 + option_pnl_pct / 100), 0)
    actual_pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    return exit_price, "TIME_EXIT", holding_days, actual_pnl_pct

def run_backtest(instrument="NIFTY", min_score=65, capital=750000):
    print(f"\n{'='*55}")
    print(f"  SmartOptions Backtester")
    print(f"  Instrument: {instrument} | Min Score: {min_score}")
    print(f"  Capital: Rs {capital:,}")
    print(f"{'='*55}\n")

    df = calculate_all_signals(instrument)
    qualifying = df[df["signal_score"] >= min_score].copy()
    print(f"Found {len(qualifying)} qualifying signals (score >= {min_score})")

    if len(qualifying) == 0:
        print("\nNo qualifying signals found at score 65.")
        print("Running with min_score=30 for demonstration...")
        qualifying = df[df["signal_score"] >= 30].copy()
        print(f"Found {len(qualifying)} signals with score >= 30")

    trades = []
    last_exit_date = None

    for entry_date, row in qualifying.iterrows():
        if last_exit_date and (entry_date - last_exit_date).days < 21:
            continue
        entry_premium = estimate_option_premium(row["close"], row["direction"])
        lot_cost = entry_premium * NIFTY_LOT_SIZE
        costs = calculate_transaction_costs(entry_premium)
        max_risk = capital * 0.02
        if lot_cost > max_risk:
            continue
        exit_price, exit_reason, days_held, pnl_pct = simulate_trade(
            df, entry_date, row["direction"], entry_premium
        )
        gross_pnl = (exit_price - entry_premium) * NIFTY_LOT_SIZE
        net_pnl = gross_pnl - costs
        trades.append({
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "direction": row["direction"],
            "signal_score": row["signal_score"],
            "nifty_close": round(row["close"], 1),
            "entry_premium": entry_premium,
            "exit_premium": round(exit_price, 1),
            "exit_reason": exit_reason,
            "days_held": days_held,
            "pnl_pct": round(pnl_pct, 1),
            "gross_pnl": round(gross_pnl, 0),
            "transaction_costs": costs,
            "net_pnl": round(net_pnl, 0),
            "is_winner": net_pnl > 0
        })
        entry_pos = df.index.tolist().index(entry_date)
        last_exit_date = df.index[min(entry_pos + days_held, len(df) - 1)]

    if not trades:
        print("No trades were simulated.")
        return None

    results_df = pd.DataFrame(trades)
    total_trades = len(results_df)
    winners = results_df["is_winner"].sum()
    losers = total_trades - winners
    win_rate = (winners / total_trades) * 100
    total_net_pnl = results_df["net_pnl"].sum()
    avg_winner = results_df[results_df["is_winner"]]["net_pnl"].mean()
    avg_loser = results_df[~results_df["is_winner"]]["net_pnl"].mean()
    total_costs = results_df["transaction_costs"].sum()
    stops = len(results_df[results_df["exit_reason"] == "STOP_LOSS"])
    targets = len(results_df[results_df["exit_reason"] == "TARGET"])
    time_exits = len(results_df[results_df["exit_reason"] == "TIME_EXIT"])

    print(f"\n{'='*55}")
    print(f"  BACKTEST RESULTS SUMMARY")
    print(f"{'='*55}")
    print(f"  Period:          {results_df['entry_date'].iloc[0]} to {results_df['entry_date'].iloc[-1]}")
    print(f"  Total Trades:    {total_trades}")
    print(f"  Winners:         {winners} ({win_rate:.1f}%)")
    print(f"  Losers:          {losers} ({100-win_rate:.1f}%)")
    print(f"{'─'*55}")
    print(f"  Total Net P&L:   Rs {total_net_pnl:,.0f}")
    print(f"  Avg Winner:      Rs {avg_winner:,.0f}")
    print(f"  Avg Loser:       Rs {avg_loser:,.0f}")
    print(f"  Total Costs:     Rs {total_costs:,.0f}")
    print(f"{'─'*55}")
    print(f"  Stop Loss Hits:  {stops} ({stops/total_trades*100:.0f}%)")
    print(f"  Targets Hit:     {targets} ({targets/total_trades*100:.0f}%)")
    print(f"  Time Exits:      {time_exits} ({time_exits/total_trades*100:.0f}%)")
    print(f"{'='*55}")

    if win_rate >= 55:
        print(f"\n  RESULT: STRATEGY QUALIFIES (win rate >= 55%)")
    else:
        print(f"\n  RESULT: Strategy needs improvement (win rate < 55%)")
        print(f"  This is normal — we add VIX and PCR signals next.")

    print(f"\n  Last 10 trades:")
    print(f"  {'Date':<12} {'Dir':<9} {'Score':<7} {'Exit':<12} {'Net P&L':>10}")
    print(f"  {'─'*54}")
    for _, t in results_df.tail(10).iterrows():
        print(f"  {t['entry_date']:<12} {t['direction']:<9} {t['signal_score']:<7} {t['exit_reason']:<12} Rs {t['net_pnl']:>7,.0f}")

    return results_df

if __name__ == "__main__":
    run_backtest(instrument="NIFTY", min_score=65, capital=750000)
