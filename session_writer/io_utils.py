from __future__ import annotations

from datetime import datetime
from pathlib import Path


def now_start_string() -> str:
    current = datetime.now()
    month = current.month
    day = current.day
    year = current.year % 100
    hour = current.hour % 12
    if hour == 0:
        hour = 12
    ampm = "am" if current.hour < 12 else "pm"
    return f"{month}/{day}/{year:02d} {hour}:{current.minute:02d}{ampm}"
