import json
import requests
import os
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent.parent

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK"]

GEX_FILE = BASE_DIR / "output" / "gex_levels.json"

LAST_FILE = BASE_DIR / "output" / "last_discord_levels.json"


def load_levels():

    with open(
        GEX_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    full = data["full_chain"]

    return {
        "gamma_flip": round(
            float(full["gamma_flip_nq"]),
            2
        ),

        "call_wall": round(
            float(full["call_wall_nq"]),
            2
        ),

        "put_wall": round(
            float(full["put_wall_nq"]),
            2
        ),

        "max_pain": round(
            float(full["max_pain_nq"]),
            2
        ),
    }


def load_previous_levels():

    if not LAST_FILE.exists():

        return None

    try:

        with open(
            LAST_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return None


def save_levels(levels):

    with open(
        LAST_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            levels,
            f,
            indent=2
        )


def find_changes(
    old,
    new
):

    if old is None:

        return [
            "gamma_flip",
            "call_wall",
            "put_wall",
            "max_pain"
        ]

    return [
        key
        for key in new
        if new[key] != old.get(key)
    ]


def send_discord(
    levels,
    changed_levels
):

    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    copy_line = (
        f"{levels['gamma_flip']}, "
        f"{levels['call_wall']}, "
        f"{levels['put_wall']}, "
        f"{levels['max_pain']}"
    )

    changed_names = {
        "gamma_flip": "Gamma Flip",
        "call_wall": "Call Wall",
        "put_wall": "Put Wall",
        "max_pain": "Max Pain",
    }

    changes_text = "\n".join(
        f"• **{changed_names[key]}** → `{levels[key]}`"
        for key in changed_levels
    )

    payload = {

        "content": (
            f"{copy_line}\n\n"
            "NQ GEX UPDATE"
        ),

        "embeds": [

            {

                "title":
                    "NQ GEX UPDATE",

                "description":
                    "**NEW LEVELS PUBLISHED**",

                "color":
                    5793266,

                "fields": [

                    {
                        "name":
                            "Gamma Flip",

                        "value":
                            f"`{levels['gamma_flip']}`",

                        "inline":
                            True
                    },

                    {
                        "name":
                            "Call Wall",

                        "value":
                            f"`{levels['call_wall']}`",

                        "inline":
                            True
                    },

                    {
                        "name":
                            "Put Wall",

                        "value":
                            f"`{levels['put_wall']}`",

                        "inline":
                            True
                    },

                    {
                        "name":
                            "Max Pain",

                        "value":
                            f"`{levels['max_pain']}`",

                        "inline":
                            True
                    },

                    {
                        "name":
                            "Changed",

                        "value":
                            changes_text,

                        "inline":
                            False
                    }

                ],

                "footer": {
                    "text":
                        "NQ GEX Engine"
                },

                "timestamp":
                    timestamp
            }
        ]
    }

    response = requests.post(
        WEBHOOK_URL,
        json=payload,
        timeout=10
    )

    if response.ok:

        print(
            "Discord GEX update sent successfully."
        )

    else:

        print(
            "Discord update failed."
        )

        print(
            "Status:",
            response.status_code
        )

        print(
            response.text
        )


def main():

    levels = load_levels()

    previous = load_previous_levels()

    changed_levels = find_changes(
        previous,
        levels
    )

    if not changed_levels:

        print(
            "No GEX levels changed. "
            "Discord notification skipped."
        )

        return

    print(
        "GEX level change detected:"
    )

    for key in changed_levels:

        print(
            f"  {key}: {levels[key]}"
        )

    send_discord(
        levels,
        changed_levels
    )

    save_levels(
        levels
    )


if __name__ == "__main__":

    main()
