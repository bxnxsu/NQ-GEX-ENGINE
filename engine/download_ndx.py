import json
import requests
from datetime import datetime
from pathlib import Path


URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_NDX.json"

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "ndx_options.json"


def download_options():
    print("Downloading NDX options data...")

    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    data = response.json()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "downloaded_at": datetime.now().isoformat(),
        "source": URL,
        "data": data
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print()
    print("SUCCESS")
    print("Saved to:")
    print(OUTPUT_FILE)
    print()
    print("File size:", OUTPUT_FILE.stat().st_size, "bytes")


if __name__ == "__main__":
    download_options()
