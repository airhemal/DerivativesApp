import os
from dotenv import load_dotenv

load_dotenv()

# API Credentials
BREEZE_API_KEY = os.getenv("BREEZE_API_KEY")
BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET")
BREEZE_SESSION_TOKEN = os.getenv("BREEZE_SESSION_TOKEN")

# Capital Settings
CAPITAL = int(os.getenv("CAPITAL", 750000))
MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", 2.0))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 3))
MONTHLY_LOSS_LIMIT = int(os.getenv("MONTHLY_LOSS_LIMIT", 50000))

# Risk Rules
STOP_LOSS_PCT = 50        # Exit when option loses 50% of premium
TARGET_PCT = 100          # Exit when option gains 100%
MIN_DAYS_TO_EXPIRY = 21   # Never enter with less than 21 days
FORCE_EXIT_DAYS = 5       # Force exit this many days before expiry
MIN_SIGNAL_SCORE = 65     # Minimum score to suggest a trade
VIX_MAX = 25              # No new trades above this VIX level
IVR_MAX = 60              # No buying options above this IV Rank

# Instruments
INSTRUMENTS = ["NIFTY", "BANKNIFTY"]

# Database
DB_PATH = "data/smartoptions.db"
