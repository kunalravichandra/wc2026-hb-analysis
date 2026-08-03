# scripts/test_fbref.py
"""
Module: test_fbref.py
Purpose: Test FBref connectivity and identify the correct URL
         structure for WC 2026 match pages before building
         the full scraper. Run this once to confirm access
         and understand the page structure.
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

# This is how we identify ourselves to FBref's servers
# Using a real browser user agent reduces the chance of being blocked
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive"
}

# FBref World Cup 2026 competition page
# This is the starting point — from here we find individual match URLs
WC_2026_URL = "https://fbref.com/en/comps/1/World-Cup-Stats"

# Wait time between requests — never lower this
REQUEST_DELAY = 5


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> BeautifulSoup | None:
    """
    Fetch a single page from FBref using a persistent session.
    A session object maintains cookies and connection state
    across requests, making them look more like a real browser.

    Args:
        url: Full URL of the page to fetch.

    Returns:
        BeautifulSoup object of the parsed page, or None on failure.
    """
    print(f"Fetching: {url}")

    # A session persists cookies between requests
    # This is important because FBref sets cookies on first visit
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
    })

    try:
        # First visit the FBref homepage to get cookies
        # exactly like a real browser would
        session.get("https://fbref.com/en/", timeout=15)
        time.sleep(3)

        # Now request the actual page we want
        response = session.get(url, timeout=15)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            time.sleep(REQUEST_DELAY)
            return BeautifulSoup(response.content, "lxml")

        elif response.status_code == 429:
            print("Rate limited — waiting 60 seconds...")
            time.sleep(60)
            return None

        else:
            print(f"Status {response.status_code} — blocked")
            return None

    except requests.exceptions.RequestException as exc:
        print(f"Request failed: {exc}")
        return None


def find_match_links(soup: BeautifulSoup) -> list:
    """
    Find all individual match report links on the WC 2026 page.
    FBref uses anchor tags with '/en/matches/' in the href
    to link to individual match report pages.

    Args:
        soup: Parsed HTML of the competition page.

    Returns:
        List of full URLs to individual match report pages.
    """
    match_links = []
    base_url = "https://fbref.com"

    # Find all anchor tags that link to match reports
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Match report links contain '/en/matches/' in the path
        if "/en/matches/" in href and href not in match_links:
            full_url = base_url + href if href.startswith("/") else href
            match_links.append(full_url)

    return match_links


def inspect_match_page(url: str) -> None:
    """
    Fetch a single match page and print all table IDs found.
    This tells us exactly which tables are available and what
    to target in our full scraper.

    Args:
        url: Full URL of a single match report page.
    """
    soup = fetch_page(url)

    if not soup:
        print("Failed to fetch match page.")
        return

    print("\n" + "=" * 55)
    print("TABLES FOUND ON MATCH PAGE")
    print("=" * 55)

    # Find all HTML tables and print their IDs
    tables = soup.find_all("table")
    print(f"Total tables found: {len(tables)}")

    for table in tables:
        table_id = table.get("id", "NO ID")
        caption = table.find("caption")
        caption_text = caption.get_text(strip=True) if caption else "No caption"
        print(f"  Table ID: {table_id:<45} Caption: {caption_text}")

    print("\n" + "=" * 55)
    print("SCORE BOX CONTENT")
    print("=" * 55)

    # The scorebox div contains match summary info
    scorebox = soup.find("div", class_="scorebox")
    if scorebox:
        print(scorebox.get_text(separator=" | ", strip=True)[:500])
    else:
        print("No scorebox found")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Test FBref access using multiple strategies.
    We test individual match pages directly rather than
    the competition index page which is more heavily protected.
    """
    print("=" * 55)
    print("FBREF CONNECTIVITY TEST — REVISED APPROACH")
    print("=" * 55)

    # Test URLs to try — from least to most protected
    test_urls = [
        # Direct match page — Mexico vs South Africa was first match
        "https://fbref.com/en/matches/a3eb7a37/"
        "Mexico-South-Africa-June-11-2026-World-Cup",

        # FBref main page — baseline test
        "https://fbref.com/en/",

        # WC 2026 scores and fixtures page
        # This is different from the stats page and less protected
        "https://fbref.com/en/comps/1/schedule/"
        "World-Cup-Scores-and-Fixtures",
    ]

    for url in test_urls:
        print(f"\nTesting: {url[:70]}...")
        soup = fetch_page(url)

        if soup:
            title = soup.title.get_text() if soup.title else "No title"
            print(f"SUCCESS — Page title: {title}")

            # If we got a match page, inspect it immediately
            if "/matches/" in url:
                print("\n" + "=" * 55)
                print("MATCH PAGE TABLES FOUND")
                print("=" * 55)
                tables = soup.find_all("table")
                print(f"Total tables: {len(tables)}")
                for table in tables:
                    table_id = table.get("id", "NO ID")
                    caption = table.find("caption")
                    caption_text = (
                        caption.get_text(strip=True)
                        if caption else "No caption"
                    )
                    print(f"  {table_id:<40} {caption_text}")

                # Check scorebox
                scorebox = soup.find("div", class_="scorebox")
                if scorebox:
                    print("\nSCOREBOX FOUND:")
                    print(scorebox.get_text(separator=" | ", strip=True)[:300])
        else:
            print("BLOCKED — Status 403 or other error")

        # Always wait between requests
        print("Waiting 5 seconds before next request...")
        time.sleep(5)


if __name__ == "__main__":
    main()