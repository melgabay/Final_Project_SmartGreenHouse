# sensor_pipeline.py – JSON utilities (no more PNG)
import json
import os
from typing import Any, Dict, List, Optional

DATA_FILE = "sensor_data.json"


def load_data() -> List[Dict[str, Any]]:
    """
    Load sensor data from the local JSON file.
    Returns an empty list if the file doesn't exist or is invalid.
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def get_latest() -> Dict[str, Any]:
    """
    Return the most recent data entry from the JSON file.
    Returns an empty dictionary if the file is empty or missing.
    """
    data = load_data()
    return data[-1] if data else {}


def get_series(sensor_key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Extract a list of time series data points for a specific sensor.
    Optionally limits the number of returned entries.

    Each entry has the format:
    { "timestamp": ..., "value": ... }
    """
    data = load_data()
    if limit:
        data = data[-limit:]

    return [
        {"timestamp": row["timestamp"], "value": row.get(sensor_key)}
        for row in data
        if sensor_key in row
    ]