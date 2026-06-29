# scripts/endpoint_check.py
"""
Module: endpoint_check.py
Purpose: Check all available endpoints on football-data.org
         for WC 2026 and print the full data structure of each.
         Run this once before building the collection script
         so we know exactly what fields we have to work with.
Author: Kunal
Date: 2026
Standards: PEP8
"""

import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("FOOTBALL_DATA_KEY")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": KEY}


def check_match_detail(match_id: int) -> None:
    """
    Fetch full detail for a single match by ID.
    This is the most important check — it tells us if individual
    match endpoints give us more detail than the bulk matches list.

    Args:
        match_id: A known finished match ID from our earlier test.
    """
    print("=" * 55)
    print(f"SINGLE MATCH DETAIL — ID {match_id}")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/matches/{match_id}",
        headers=HEADERS
    )
    print("Status code:", r.status_code)
    print(json.dumps(r.json(), indent=2))


def check_team_matches(team_id: int, team_name: str) -> None:
    """
    Fetch all WC 2026 matches for a specific team.
    Some APIs give more detail at team level than competition level.

    Args:
        team_id: Team ID from our earlier exploration output.
        team_name: Human readable name for the print output.
    """
    print("\n" + "=" * 55)
    print(f"TEAM MATCHES — {team_name} (ID: {team_id})")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/teams/{team_id}/matches",
        headers=HEADERS,
        params={
            "competitions": "WC",
            "season": 2026,
            "status": "FINISHED"
        }
    )
    print("Status code:", r.status_code)

    data = r.json()
    matches = data.get("matches", [])
    print(f"Matches found: {len(matches)}")

    if matches:
        print("\nFirst match full structure:")
        print(json.dumps(matches[0], indent=2))


def check_match_head2head(match_id: int) -> None:
    """
    Check if head-to-head data is available for a match.
    This might give us historical context between two teams.

    Args:
        match_id: A known finished match ID.
    """
    print("\n" + "=" * 55)
    print(f"HEAD TO HEAD — Match ID {match_id}")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/matches/{match_id}/head2head",
        headers=HEADERS
    )
    print("Status code:", r.status_code)

    data = r.json()
    print(json.dumps(data, indent=2))


def check_scorers() -> None:
    """
    Check top scorers endpoint — may give us goal timing data.
    """
    print("\n" + "=" * 55)
    print("TOP SCORERS")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/competitions/WC/scorers",
        headers=HEADERS,
        params={"season": 2026}
    )
    print("Status code:", r.status_code)

    data = r.json()
    scorers = data.get("scorers", [])
    print(f"Scorers found: {len(scorers)}")

    if scorers:
        print("\nTop 3 scorers:")
        for scorer in scorers[:3]:
            print(json.dumps(scorer, indent=2))


def main() -> None:
    """
    Run all endpoint checks in sequence.
    We use match ID 537327 which is Mexico vs South Africa —
    the first finished match we confirmed in our earlier test.
    Brazil (ID 764) is used for the team check.
    """
    # Check individual match detail
    check_match_detail(match_id=537327)

    # Check team-level match data using Brazil as example
    check_team_matches(team_id=764, team_name="Brazil")

    # Check head to head
    check_match_head2head(match_id=537327)

    # Check scorers
    check_scorers()

    print("\n" + "=" * 55)
    print("ENDPOINT CHECK COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    main()