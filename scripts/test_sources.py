# scripts/test_sources.py
"""
Module: test_sources.py
Purpose: Test all remaining free data sources for WC 2026
         match statistics and events data.
         We test Understat, WhoScored, and Sofascore to find
         which one is accessible and has the data we need.
Author: Kunal
Date: 2026
Standards: PEP8
"""

import requests
import time
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REQUEST_DELAY = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1"
}


# ---------------------------------------------------------------------------
# Generic fetch function
# ---------------------------------------------------------------------------

def fetch_page(url: str,
               session: requests.Session = None) -> tuple:
    """
    Fetch a URL and return status code and BeautifulSoup object.
    Using a tuple return lets us check the status code even on failure.

    Args:
        url: Full URL to fetch.
        session: Optional requests Session for cookie persistence.

    Returns:
        Tuple of (status_code, BeautifulSoup or None).
    """
    try:
        requester = session if session else requests
        response = requester.get(url, headers=HEADERS, timeout=15)
        time.sleep(REQUEST_DELAY)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "lxml")
            return response.status_code, soup

        return response.status_code, None

    except requests.exceptions.RequestException as exc:
        print(f"  Request error: {exc}")
        return 0, None


# ---------------------------------------------------------------------------
# Source 1 — Understat
# ---------------------------------------------------------------------------

def test_understat() -> None:
    """
    Test Understat.com for WC 2026 xG and match data.
    Understat is known for clean xG data and has a semi-structured
    JavaScript data layer embedded in its pages.
    """
    print("\n" + "=" * 55)
    print("SOURCE 1 — UNDERSTAT.COM")
    print("=" * 55)

    # Understat organises by league/tournament
    # We check if they cover the World Cup
    urls_to_test = [
        "https://understat.com",
        "https://understat.com/league/World_Cup",
        "https://understat.com/league/World_Cup/2026",
    ]

    for url in urls_to_test:
        print(f"\nTesting: {url}")
        status, soup = fetch_page(url)
        print(f"Status: {status}")

        if soup:
            title = soup.title.get_text() if soup.title else "No title"
            print(f"Title: {title}")

            # Check if there is any match data on the page
            tables = soup.find_all("table")
            print(f"Tables found: {len(tables)}")


# ---------------------------------------------------------------------------
# Source 2 — WhoScored
# ---------------------------------------------------------------------------

def test_whoscored() -> None:
    """
    Test WhoScored.com for WC 2026 match statistics.
    WhoScored provides detailed match ratings and statistics
    including possession, shots, cards and substitutions.
    """
    print("\n" + "=" * 55)
    print("SOURCE 2 — WHOSCORED.COM")
    print("=" * 55)

    urls_to_test = [
        "https://www.whoscored.com",
        "https://www.whoscored.com/Tournaments/36/Show/International-FIFA-World-Cup",
    ]

    session = requests.Session()
    session.headers.update(HEADERS)

    for url in urls_to_test:
        print(f"\nTesting: {url}")
        status, soup = fetch_page(url, session=session)
        print(f"Status: {status}")

        if soup:
            title = soup.title.get_text() if soup.title else "No title"
            print(f"Title: {title}")
            tables = soup.find_all("table")
            print(f"Tables found: {len(tables)}")


# ---------------------------------------------------------------------------
# Source 3 — Sofascore
# ---------------------------------------------------------------------------

def test_sofascore() -> None:
    """
    Test Sofascore for WC 2026 match timeline and statistics.
    Sofascore has a public API that powers their mobile app —
    this is sometimes accessible without authentication.
    """
    print("\n" + "=" * 55)
    print("SOURCE 3 — SOFASCORE API")
    print("=" * 55)

    # Sofascore exposes a REST API for their app
    # Tournament ID 16 is typically the FIFA World Cup
    urls_to_test = [
        # Main website test
        "https://www.sofascore.com",

        # Their public app API — this is what powers their mobile app
        # and is often accessible for research purposes
        "https://api.sofascore.com/api/v1/unique-tournament/16/season/58587/events/last/0",

        # Alternative tournament ID
        "https://api.sofascore.com/api/v1/unique-tournament/16/seasons",
    ]

    api_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com"
    }

    for url in urls_to_test:
        print(f"\nTesting: {url[:70]}")
        try:
            response = requests.get(url, headers=api_headers, timeout=15)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                content_type = response.headers.get(
                    "Content-Type", ""
                )

                if "application/json" in content_type:
                    data = response.json()
                    print("JSON response received")
                    # Print top level keys so we know what is available
                    if isinstance(data, dict):
                        print(f"Top level keys: {list(data.keys())}")
                else:
                    soup = BeautifulSoup(response.content, "lxml")
                    title = (
                        soup.title.get_text()
                        if soup.title else "No title"
                    )
                    print(f"HTML page title: {title}")

            time.sleep(REQUEST_DELAY)

        except requests.exceptions.RequestException as exc:
            print(f"Request error: {exc}")


# ---------------------------------------------------------------------------
# Source 4 — The Sports DB
# ---------------------------------------------------------------------------

def test_sportsdb() -> None:
    """
    Test TheSportsDB free API for WC 2026 match events.
    TheSportsDB is a community database with a free API tier
    that includes some event-level match data.
    """
    print("\n" + "=" * 55)
    print("SOURCE 4 — THESPORTSDB API")
    print("=" * 55)

    # TheSportsDB free API endpoints
    # League ID 4429 is FIFA World Cup in their system
    urls_to_test = [
        "https://www.thesportsdb.com/api/v1/json/3/search_all_leagues.php?c=International&s=Soccer",
        "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4429&s=2026",
        "https://www.thesportsdb.com/api/v1/json/3/lookupleague.php?id=4429",
    ]

    for url in urls_to_test:
        print(f"\nTesting: {url[:70]}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"Top level keys: {list(data.keys())}")

                # Check first key to see if data exists
                first_key = list(data.keys())[0] if data else None
                if first_key and data[first_key]:
                    first_item = data[first_key][0] if isinstance(
                        data[first_key], list
                    ) else data[first_key]
                    print(
                        f"Sample data keys: "
                        f"{list(first_item.keys())[:10]}"
                        if isinstance(first_item, dict)
                        else f"Data: {str(first_item)[:100]}"
                    )
                else:
                    print("No data returned for this endpoint")

            time.sleep(REQUEST_DELAY)

        except requests.exceptions.RequestException as exc:
            print(f"Request error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run connectivity tests for all alternative data sources.
    Results tell us which sources are accessible and what
    data they provide for WC 2026 match statistics.
    """
    print("=" * 55)
    print("ALTERNATIVE SOURCE CONNECTIVITY TESTS")
    print("=" * 55)
    print("Testing 4 sources — this will take about 2 minutes")
    print("due to polite delays between requests.")

    test_understat()
    test_whoscored()
    test_sofascore()
    test_sportsdb()

    print("\n" + "=" * 55)
    print("ALL TESTS COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    main()