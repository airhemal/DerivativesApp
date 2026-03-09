import sqlite3
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smartoptions_config.settings import DB_PATH

def get_connection():
    """Get a connection to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def setup_database():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: Raw price data for Nifty and BankNifty
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            UNIQUE(instrument, date)
        )
    ''')

    # Table 2: Every trade suggestion the agent generates
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            instrument TEXT NOT NULL,
            direction TEXT NOT NULL,
            strike REAL,
            expiry TEXT,
            entry_price REAL,
            score INTEGER,
            signal_breakdown TEXT,
            status TEXT DEFAULT "PENDING",
            expiry_reason TEXT
        )
    ''')

    # Table 3: Actual outcomes of approved trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suggestion_id INTEGER,
            approved_at TEXT,
            actual_entry_price REAL,
            slippage_pct REAL,
            exit_price REAL,
            exit_reason TEXT,
            gross_pnl REAL,
            net_pnl REAL,
            holding_days INTEGER,
            FOREIGN KEY(suggestion_id) REFERENCES trade_suggestions(id)
        )
    ''')

    # Table 4: Daily market regime log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_regime_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            regime TEXT,
            vix REAL,
            adx REAL,
            nifty_close REAL,
            fii_net INTEGER,
            notes TEXT
        )
    ''')

    # Table 5: Portfolio health snapshot
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            open_positions INTEGER DEFAULT 0,
            capital_deployed REAL DEFAULT 0,
            monthly_pnl REAL DEFAULT 0,
            consecutive_losses INTEGER DEFAULT 0,
            mode TEXT DEFAULT "NORMAL"
        )
    ''')

    # Table 6: Signal performance tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_name TEXT,
            period TEXT,
            trades_count INTEGER DEFAULT 0,
            win_count INTEGER DEFAULT 0,
            avg_pnl REAL DEFAULT 0,
            last_updated TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("Database setup complete. All tables created.")

if __name__ == "__main__":
    setup_database()
