from datetime import datetime
from typing import Dict

# Application Metrics Tracker
APP_METRICS: Dict[str, int] = {
    "total_requests": 0,
    "cache_hits": 0,
    "api_errors": 0,
}

APP_START_TIME = datetime.now()
