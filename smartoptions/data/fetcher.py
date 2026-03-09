import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from breeze_connect import BreezeConnect
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smartoptions_config.settings import (BREEZE_API_KEY, BREEZE_API_SECRET, 
                              BREEZE_SESSION_TOKEN, INSTRUMENTS)
from data.database import get_connection

def connect_breeze():
    """Connect to Breeze API and return the connection object."""
    print("Connecting to Breeze API...")
    breeze = BreezeConnect(api_key=BREEZE_API_KEY)
    breeze.generate_session(
        api_secret=BREEZE_API_SECRET,
        session_token=BREEZE_SESSION_TOKEN
    )
    print("Connected successfully!")
    return breeze

def fetch_historical_data(breeze, instrument, from_date, to_date):
    """Fetch daily OHLCV data for a given instrument and date range."""
    print(f"Fetching {instrument} data from {from_date} to {to_date}...")
    
    response = breeze.get_historical_data_v2(
        interval="1day",
        from_date=from_date,
        to_date=to_date,
        stock_code=instrument,
        exchange_code="NSE",
        product_type="cash"
    )
    
    if response and response.get("Status") == 200:
        data = response.get("Success", [])
        if data:
            df = pd.DataFrame(data)
            df["instrument"] = instrument
            print(f"  Got {len(df)} records for {instrument}")
            return df
        else:
            print(f"  No data returned for {instrument}")
            return None
    else:
        print(f"  Error fetching {instrument}: {response}")
        return None

def save_to_database(df, instrument):
    """Save fetched price data into the SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO price_data 
                (instrument, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                instrument,
                str(row.get("datetime", row.get("date", ""))),
                float(row.get("open", 0)),
                float(row.get("high", 0)),
                float(row.get("low", 0)),
                float(row.get("close", 0)),
                int(float(row.get("volume", 0)))
            ))
            if cursor.rowcount > 0:
                saved += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Row error: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"  Saved {saved} new records, skipped {skipped} duplicates")

def run_initial_download():
    """Download 3 years of historical data for all instruments."""
    print("\n=== SmartOptions Data Fetcher ===")
    print("Starting initial historical data download...")
    
    # Date range: 3 years back to today
    to_date = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
    from_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%dT00:00:00.000Z")
    
    print(f"Date range: {from_date[:10]} to {to_date[:10]}")
    
    # Connect to Breeze
    breeze = connect_breeze()
    
    # Fetch data for each instrument
    for instrument in INSTRUMENTS:
        print(f"\nProcessing {instrument}...")
        df = fetch_historical_data(breeze, instrument, from_date, to_date)
        if df is not None:
            save_to_database(df, instrument)
    
    # Confirm what is now in the database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT instrument, COUNT(*) as records, MIN(date) as earliest, MAX(date) as latest FROM price_data GROUP BY instrument")
    rows = cursor.fetchall()
    conn.close()
    
    print("\n=== Download Complete ===")
    print(f"{'Instrument':<15} {'Records':<10} {'From':<15} {'To'}")
    print("-" * 55)
    for row in rows:
        print(f"{row[0]:<15} {row[1]:<10} {str(row[2])[:10]:<15} {str(row[3])[:10]}")

if __name__ == "__main__":
    run_initial_download()
