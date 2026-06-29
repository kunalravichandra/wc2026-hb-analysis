# scripts/test_football_data.py
"""
Quick test to check what WC 2026 data is accessible
on the football-data.org free tier.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("FOOTBALL_DATA_KEY")
headers = {"X-Auth-Token": key}

print("Testing football-data.org API...")
print("-" * 40)

r = requests.get(
    "https://api.football-data.org/v4/competitions/WC/matches",
    headers=headers
)

data = r.json()
print("Status code:", r.status_code)

if r.status_code == 200:
    matches = data.get("matches", [])
    print(f"Total matches found: {len(matches)}")

    if matches:
        print("\nSample match:")
        m = matches[0]
        print("  Home team :", m["homeTeam"]["name"])
        print("  Away team :", m["awayTeam"]["name"])
        print("  Date      :", m["utcDate"])
        print("  Status    :", m["status"])
        print("  Score     :", m["score"]["fullTime"])

elif r.status_code == 403:
    print("Access denied — WC 2026 is not included in the free tier")
    print("Message:", data.get("message", "No message returned"))

elif r.status_code == 404:
    print("Competition not found")
    print("Message:", data.get("message", "No message returned"))

elif r.status_code == 401:
    print("Unauthorised — check your FOOTBALL_DATA_KEY in .env file")

else:
    print("Unexpected response:")
    print(data)