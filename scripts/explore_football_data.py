# scripts/explore_football_data.py
"""
Module: explore_football_data.py
Purpose: Explore the full structure of data available from
         football-data.org for WC 2026 before building the
         main collection pipeline. Run this once to understand
         what fields are available.
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


def explore_competition() -> None:
    """Fetch top-level competition info for WC 2026."""
    print("=" * 55)
    print("COMPETITION INFO")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/competitions/WC",
        headers=HEADERS
    )
    data = r.json()

    print("Name        :", data.get("name"))
    print("Area        :", data.get("area", {}).get("name"))
    print("Start Date  :", data.get("currentSeason", {}).get("startDate"))
    print("End Date    :", data.get("currentSeason", {}).get("endDate"))
    print("Match day   :", data.get("currentSeason", {}).get(
        "currentMatchday")
    )


def explore_matches() -> None:
    """
    Fetch all matches and show full field structure of one match.
    This tells us exactly what data is available per match.
    """
    print("\n" + "=" * 55)
    print("MATCH DATA STRUCTURE")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/competitions/WC/matches",
        headers=HEADERS
    )
    data = r.json()
    matches = data.get("matches", [])

    print(f"Total matches available : {len(matches)}")

    # Count by status
    status_counts = {}
    for m in matches:
        status = m.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

    print("\nMatches by status:")
    for status, count in status_counts.items():
        print(f"  {status:<20} {count} matches")

    # Show full structure of one finished match
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    if finished:
        print("\nFull field structure of one finished match:")
        print("-" * 55)
        print(json.dumps(finished[0], indent=2))


def explore_teams() -> None:
    """Fetch all teams in WC 2026."""
    print("\n" + "=" * 55)
    print("TEAMS IN WC 2026")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/competitions/WC/teams",
        headers=HEADERS
    )
    data = r.json()
    teams = data.get("teams", [])

    print(f"Total teams: {len(teams)}")
    print("\nTeam list:")
    for team in teams:
        print(f"  ID: {team['id']:<6} Name: {team['name']}")


def explore_standings() -> None:
    """Fetch group stage standings."""
    print("\n" + "=" * 55)
    print("GROUP STANDINGS")
    print("=" * 55)

    r = requests.get(
        f"{BASE_URL}/competitions/WC/standings",
        headers=HEADERS
    )
    data = r.json()
    standings = data.get("standings", [])

    for group in standings:
        print(f"\n{group.get('group', 'Unknown group')}")
        print("-" * 35)
        for entry in group.get("table", []):
            team = entry["team"]["name"]
            pts = entry["points"]
            played = entry["playedGames"]
            gf = entry["goalsFor"]
            ga = entry["goalsAgainst"]
            print(f"  {team:<25} Pts:{pts}  P:{played}  "
                  f"GF:{gf}  GA:{ga}")


def main() -> None:
    """Run all exploration functions in sequence."""
    explore_competition()
    explore_matches()
    explore_teams()
    explore_standings()
    print("\n" + "=" * 55)
    print("EXPLORATION COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    main()