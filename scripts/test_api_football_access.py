# scripts/test_api_football_access.py
"""
Module: test_api_football_access.py
Purpose: Test what WC 2026 data is now accessible on the
         API-Football free tier following tournament completion.
         Checks fixtures, match statistics, events, and lineups
         for a known completed match.
Author: Kunal
Date: 2026
Standards: PEP8
"""

import requests
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
WC_LEAGUE_ID = 1
WC_SEASON = 2026
REQUEST_DELAY = 2

HEADERS = {
    "x-apisports-key": API_KEY,
    "x-apisports-host": "v3.football.api-sports.io"
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def fetch(endpoint: str, params: dict = None) -> dict | None:
    """
    Make a GET request to API-Football.

    Args:
        endpoint: API endpoint path e.g. '/fixtures'
        params: Optional query parameters.

    Returns:
        Parsed JSON response or None on failure.
    """
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=10
        )
        time.sleep(REQUEST_DELAY)

        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for API-level errors inside the response
            if data.get("errors"):
                print(f"  API errors: {data['errors']}")
                return None

            return data

        return None

    except requests.exceptions.RequestException as exc:
        print(f"  Request error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def check_quota() -> None:
    """Check remaining API quota before running tests."""
    print("=" * 55)
    print("API QUOTA CHECK")
    print("=" * 55)

    data = fetch("/status")

    if not data:
        print("Could not reach API. Check your API key.")
        return

    info = data.get("response", {})
    account = info.get("account", {})
    requests_info = info.get("requests", {})

    print(f"Account     : {account.get('firstname')} "
          f"{account.get('lastname')}")
    print(f"Plan        : {account.get('plan')}")
    print(f"Used today  : {requests_info.get('current')}")
    print(f"Daily limit : {requests_info.get('limit_day')}")
    print(f"Remaining   : "
          f"{requests_info.get('limit_day', 0) - requests_info.get('current', 0)}")


def test_fixtures() -> str | None:
    """
    Test if WC 2026 fixtures are accessible on the free tier.
    Returns the first finished fixture ID for downstream tests.

    Returns:
        First finished fixture ID as string, or None if not accessible.
    """
    print("\n" + "=" * 55)
    print("TEST 1 — FIXTURES")
    print("=" * 55)

    data = fetch(
        "/fixtures",
        params={"league": WC_LEAGUE_ID, "season": WC_SEASON}
    )

    if not data:
        print("RESULT: Fixtures not accessible on free tier.")
        return None

    response = data.get("response", [])
    print(f"RESULT: {len(response)} fixtures returned")

    if not response:
        print("Empty response — likely still paywalled.")
        return None

    # Count by status
    finished = [
        f for f in response
        if f["fixture"]["status"]["short"] == "FT"
    ]
    print(f"Finished matches: {len(finished)}")

    # Show sample
    if finished:
        sample = finished[0]
        fixture_id = sample["fixture"]["id"]
        home = sample["teams"]["home"]["name"]
        away = sample["teams"]["away"]["name"]
        score_h = sample["goals"]["home"]
        score_a = sample["goals"]["away"]
        print(f"Sample: {home} {score_h}-{score_a} {away}")
        print(f"Fixture ID for detail tests: {fixture_id}")
        return str(fixture_id)

    return None


def test_match_statistics(fixture_id: str) -> None:
    """
    Test if per-team match statistics are accessible.
    This includes possession, shots, passes, cards etc.

    Args:
        fixture_id: A known finished fixture ID.
    """
    print("\n" + "=" * 55)
    print(f"TEST 2 — MATCH STATISTICS (Fixture {fixture_id})")
    print("=" * 55)

    data = fetch("/fixtures/statistics", params={"fixture": fixture_id})

    if not data:
        print("RESULT: Match statistics not accessible.")
        return

    response = data.get("response", [])

    if not response:
        print("RESULT: Empty response — likely paywalled.")
        return

    print(f"RESULT: Statistics returned for {len(response)} teams")
    print("\nAll available stat types:")
    for team_data in response:
        team_name = team_data["team"]["name"]
        print(f"\n  {team_name}:")
        for stat in team_data["statistics"]:
            print(f"    {stat['type']:<35} {stat['value']}")


def test_match_events(fixture_id: str) -> None:
    """
    Test if match events are accessible.
    Events include goals, substitutions, and cards
    with exact minute timestamps — critical for HB analysis.

    Args:
        fixture_id: A known finished fixture ID.
    """
    print("\n" + "=" * 55)
    print(f"TEST 3 — MATCH EVENTS (Fixture {fixture_id})")
    print("=" * 55)

    data = fetch("/fixtures/events", params={"fixture": fixture_id})

    if not data:
        print("RESULT: Match events not accessible.")
        return

    response = data.get("response", [])

    if not response:
        print("RESULT: Empty response — likely paywalled.")
        return

    print(f"RESULT: {len(response)} events returned")
    print("\nAll events with minutes:")
    for event in response:
        minute = event["time"]["elapsed"]
        extra = event["time"].get("extra")
        team = event["team"]["name"]
        event_type = event["type"]
        detail = event["detail"]
        player = event["player"]["name"] if event.get("player") else "N/A"

        minute_str = (
            f"{minute}+{extra}" if extra else f"{minute}"
        )
        print(
            f"  {minute_str:<8} {team:<25} "
            f"{event_type:<15} {detail:<20} {player}"
        )


def test_match_lineups(fixture_id: str) -> None:
    """
    Test if lineup and formation data is accessible.

    Args:
        fixture_id: A known finished fixture ID.
    """
    print("\n" + "=" * 55)
    print(f"TEST 4 — LINEUPS (Fixture {fixture_id})")
    print("=" * 55)

    data = fetch("/fixtures/lineups", params={"fixture": fixture_id})

    if not data:
        print("RESULT: Lineup data not accessible.")
        return

    response = data.get("response", [])

    if not response:
        print("RESULT: Empty response — likely paywalled.")
        return

    print(f"RESULT: Lineup data returned for {len(response)} teams")
    for team_data in response:
        team_name = team_data["team"]["name"]
        formation = team_data.get("formation", "Unknown")
        starters = team_data.get("startXI", [])
        print(f"\n  {team_name} — Formation: {formation}")
        print(f"  Starters: {len(starters)} players")
        if starters:
            for player in starters[:3]:
                p = player["player"]
                print(
                    f"    {p.get('number', '?'):<4} "
                    f"{p.get('name', '?'):<25} "
                    f"{p.get('pos', '?')}"
                )
            print(f"    ... and {len(starters) - 3} more")


def test_player_statistics(fixture_id: str) -> None:
    """
    Test if player level statistics are accessible.
    These include individual passing, dribbling, and
    defensive stats that support advanced analysis.

    Args:
        fixture_id: A known finished fixture ID.
    """
    print("\n" + "=" * 55)
    print(f"TEST 5 — PLAYER STATS (Fixture {fixture_id})")
    print("=" * 55)

    data = fetch(
        "/fixtures/players",
        params={"fixture": fixture_id}
    )

    if not data:
        print("RESULT: Player statistics not accessible.")
        return

    response = data.get("response", [])

    if not response:
        print("RESULT: Empty response — likely paywalled.")
        return

    print(f"RESULT: Player stats for {len(response)} teams")
    for team_data in response:
        team_name = team_data["team"]["name"]
        players = team_data.get("players", [])
        print(f"\n  {team_name} — {len(players)} players")

        if players:
            # Show stats for first player as sample
            p = players[0]
            print(f"  Sample player: {p['player']['name']}")
            stats = p.get("statistics", [{}])[0]
            print(f"  Available stat categories: "
                  f"{list(stats.keys())}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run all API-Football access tests for WC 2026 data.
    Tests five endpoints in sequence, using one request each.
    Total quota used: 6 requests (1 status + 5 tests).
    """
    print("=" * 55)
    print("API-FOOTBALL WC 2026 ACCESS TEST")
    print("Tournament ended July 19 2026")
    print("Testing if free tier now includes completed data")
    print("=" * 55)

    # Check quota first — we use 6 requests total
    check_quota()

    # Test fixtures — this gives us a fixture ID for other tests
    fixture_id = test_fixtures()

    if not fixture_id:
        print("\n" + "=" * 55)
        print("FIXTURES NOT ACCESSIBLE")
        print("Free tier does not yet include WC 2026 data.")
        print("Options:")
        print("  1. Wait a few more days and retry")
        print("  2. Proceed with TheSportsDB deep exploration")
        print("  3. Consider one month paid tier (~$15)")
        print("=" * 55)
        return

    # If fixtures are accessible, test all detail endpoints
    test_match_statistics(fixture_id)
    test_match_events(fixture_id)
    test_match_lineups(fixture_id)
    test_player_statistics(fixture_id)

    print("\n" + "=" * 55)
    print("ACCESS TEST COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    main()