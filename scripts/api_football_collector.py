# scripts/api_football_collector.py
"""
Module: api_football_collector.py
Purpose: Collect FIFA World Cup 2026 match data from API-Football.
         Pulls fixtures, match statistics, lineups, and match events.
         Designed to run incrementally — safe to run daily without
         duplicating data already collected.
Author: Kunal
Date: 2026
Standards: PEP8
"""

import os
import time
import logging
import sqlite3
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Configuration — change only these values if anything needs updating
# ---------------------------------------------------------------------------

load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
WC_2026_LEAGUE_ID = 1        # Confirm this from Step 3 above
WC_2026_SEASON = 2026
DB_PATH = "data/raw/wc2026_raw.db"
LOG_PATH = "logs/api_football.log"
REQUEST_DELAY = 1.5          # Seconds between requests — do not lower this


# ---------------------------------------------------------------------------
# Logging setup — writes to both terminal and a log file simultaneously
# ---------------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def initialise_database(db_path: str) -> sqlite3.Connection:
    """
    Create SQLite database and all required tables if they do not exist.
    Running this multiple times is safe — tables are only created once.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active SQLite connection object.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS fixtures (
            fixture_id      INTEGER PRIMARY KEY,
            date            TEXT,
            venue           TEXT,
            city            TEXT,
            home_team_id    INTEGER,
            home_team_name  TEXT,
            away_team_id    INTEGER,
            away_team_name  TEXT,
            home_goals      INTEGER,
            away_goals      INTEGER,
            status          TEXT,
            round           TEXT,
            collected_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS match_statistics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id      INTEGER,
            team_id         INTEGER,
            team_name       TEXT,
            stat_type       TEXT,
            stat_value      TEXT,
            FOREIGN KEY (fixture_id) REFERENCES fixtures(fixture_id)
        );

        CREATE TABLE IF NOT EXISTS match_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id      INTEGER,
            event_minute    INTEGER,
            event_extra     INTEGER,
            team_id         INTEGER,
            team_name       TEXT,
            player_name     TEXT,
            assist_name     TEXT,
            event_type      TEXT,
            event_detail    TEXT,
            FOREIGN KEY (fixture_id) REFERENCES fixtures(fixture_id)
        );

        CREATE TABLE IF NOT EXISTS lineups (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id      INTEGER,
            team_id         INTEGER,
            team_name       TEXT,
            formation       TEXT,
            player_id       INTEGER,
            player_name     TEXT,
            player_number   INTEGER,
            player_pos      TEXT,
            is_starter      INTEGER,
            FOREIGN KEY (fixture_id) REFERENCES fixtures(fixture_id)
        );
    """)

    conn.commit()
    logger.info("Database ready at: %s", db_path)
    return conn


# ---------------------------------------------------------------------------
# API request handler
# ---------------------------------------------------------------------------

def make_api_request(endpoint: str, params: dict) -> dict | None:
    """
    Make a single GET request to API-Football with error handling.
    Automatically pauses between requests to respect rate limits.

    Args:
        endpoint: API endpoint path e.g. '/fixtures'
        params: Query parameters as a dictionary.

    Returns:
        Parsed JSON response, or None if the request failed.
    """
    headers = {
        "x-apisports-key": API_KEY,
        "x-apisports-host": "v3.football.api-sports.io"
    }
    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            logger.warning("API error on %s: %s", endpoint, data["errors"])
            return None

        time.sleep(REQUEST_DELAY)
        return data

    except requests.exceptions.RequestException as exc:
        logger.error("Request failed for %s: %s", endpoint, exc)
        return None


# ---------------------------------------------------------------------------
# Collection functions — one per data type
# ---------------------------------------------------------------------------

def collect_fixtures(conn: sqlite3.Connection) -> list:
    """
    Fetch all WC 2026 fixtures and store them in the database.
    Uses INSERT OR REPLACE so running this again updates existing rows
    rather than creating duplicates.

    Args:
        conn: Active SQLite connection.

    Returns:
        List of all fixture IDs found (including upcoming matches).
    """
    logger.info("Collecting fixtures...")

    data = make_api_request(
        "/fixtures",
        {"league": WC_2026_LEAGUE_ID, "season": WC_2026_SEASON}
    )

    if not data or not data.get("response"):
        logger.error("No fixture data returned. Check your League ID.")
        return []

    cursor = conn.cursor()
    fixture_ids = []

    for match in data["response"]:
        fixture = match["fixture"]
        teams = match["teams"]
        goals = match["goals"]
        league = match["league"]

        cursor.execute("""
            INSERT OR REPLACE INTO fixtures VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fixture["id"],
            fixture["date"],
            fixture["venue"]["name"] if fixture.get("venue") else None,
            fixture["venue"]["city"] if fixture.get("venue") else None,
            teams["home"]["id"],
            teams["home"]["name"],
            teams["away"]["id"],
            teams["away"]["name"],
            goals["home"],
            goals["away"],
            fixture["status"]["long"],
            league["round"],
            datetime.utcnow().isoformat()
        ))

        fixture_ids.append(fixture["id"])

    conn.commit()
    logger.info("Collected %d fixtures total.", len(fixture_ids))
    return fixture_ids


def get_completed_fixture_ids(conn: sqlite3.Connection) -> list:
    """
    Return only fixture IDs for matches that have finished.
    We only collect detailed stats for completed matches.

    Args:
        conn: Active SQLite connection.

    Returns:
        List of fixture IDs with status 'Match Finished'.
    """
    df = pd.read_sql_query(
        "SELECT fixture_id FROM fixtures WHERE status = 'Match Finished'",
        conn
    )
    return df["fixture_id"].tolist()


def get_already_collected_ids(conn: sqlite3.Connection,
                               table: str) -> set:
    """
    Check which fixture IDs already have data in a given table.
    This prevents re-fetching data we already have, saving API quota.

    Args:
        conn: Active SQLite connection.
        table: Table name to check (match_statistics, match_events, lineups).

    Returns:
        Set of fixture IDs already present in that table.
    """
    df = pd.read_sql_query(
        f"SELECT DISTINCT fixture_id FROM {table}", conn
    )
    return set(df["fixture_id"].tolist())


def collect_match_statistics(conn: sqlite3.Connection,
                              fixture_ids: list) -> None:
    """
    Fetch per-team match statistics for each completed fixture.
    Skips fixtures already in the database to conserve API quota.

    Args:
        conn: Active SQLite connection.
        fixture_ids: List of completed fixture IDs to process.
    """
    already_done = get_already_collected_ids(conn, "match_statistics")
    to_fetch = [f for f in fixture_ids if f not in already_done]

    if not to_fetch:
        logger.info("Match statistics: all fixtures already collected.")
        return

    logger.info(
        "Collecting match statistics for %d fixtures "
        "(%d already done, skipping)...",
        len(to_fetch), len(already_done)
    )
    cursor = conn.cursor()

    for fixture_id in tqdm(to_fetch, desc="Match stats"):
        data = make_api_request(
            "/fixtures/statistics", {"fixture": fixture_id}
        )

        if not data or not data.get("response"):
            logger.warning("No stats for fixture %d", fixture_id)
            continue

        for team_data in data["response"]:
            team_id = team_data["team"]["id"]
            team_name = team_data["team"]["name"]

            for stat in team_data["statistics"]:
                cursor.execute("""
                    INSERT INTO match_statistics
                    (fixture_id, team_id, team_name, stat_type, stat_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    fixture_id,
                    team_id,
                    team_name,
                    stat["type"],
                    str(stat["value"]) if stat["value"] is not None else None
                ))

    conn.commit()
    logger.info("Match statistics collection complete.")


def collect_match_events(conn: sqlite3.Connection,
                          fixture_ids: list) -> None:
    """
    Fetch all in-match events for each completed fixture.
    Events include goals, substitutions, yellow/red cards — all with
    exact minute timestamps, which are critical for HB window analysis.

    Args:
        conn: Active SQLite connection.
        fixture_ids: List of completed fixture IDs to process.
    """
    already_done = get_already_collected_ids(conn, "match_events")
    to_fetch = [f for f in fixture_ids if f not in already_done]

    if not to_fetch:
        logger.info("Match events: all fixtures already collected.")
        return

    logger.info(
        "Collecting match events for %d fixtures...", len(to_fetch)
    )
    cursor = conn.cursor()

    for fixture_id in tqdm(to_fetch, desc="Match events"):
        data = make_api_request(
            "/fixtures/events", {"fixture": fixture_id}
        )

        if not data or not data.get("response"):
            logger.warning("No events for fixture %d", fixture_id)
            continue

        for event in data["response"]:
            cursor.execute("""
                INSERT INTO match_events
                (fixture_id, event_minute, event_extra, team_id,
                 team_name, player_name, assist_name,
                 event_type, event_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fixture_id,
                event["time"]["elapsed"],
                event["time"].get("extra"),
                event["team"]["id"],
                event["team"]["name"],
                event["player"]["name"] if event.get("player") else None,
                event["assist"]["name"] if event.get("assist") else None,
                event["type"],
                event["detail"]
            ))

    conn.commit()
    logger.info("Match events collection complete.")


def collect_lineups(conn: sqlite3.Connection,
                    fixture_ids: list) -> None:
    """
    Fetch starting lineups and formations for each completed fixture.
    Formations are key context variables for tactical analysis around HBs.

    Args:
        conn: Active SQLite connection.
        fixture_ids: List of completed fixture IDs to process.
    """
    already_done = get_already_collected_ids(conn, "lineups")
    to_fetch = [f for f in fixture_ids if f not in already_done]

    if not to_fetch:
        logger.info("Lineups: all fixtures already collected.")
        return

    logger.info(
        "Collecting lineups for %d fixtures...", len(to_fetch)
    )
    cursor = conn.cursor()

    for fixture_id in tqdm(to_fetch, desc="Lineups"):
        data = make_api_request(
            "/fixtures/lineups", {"fixture": fixture_id}
        )

        if not data or not data.get("response"):
            logger.warning("No lineup data for fixture %d", fixture_id)
            continue

        for team_data in data["response"]:
            team_id = team_data["team"]["id"]
            team_name = team_data["team"]["name"]
            formation = team_data.get("formation", "Unknown")

            for player in team_data.get("startXI", []):
                p = player["player"]
                cursor.execute("""
                    INSERT INTO lineups
                    (fixture_id, team_id, team_name, formation,
                     player_id, player_name, player_number,
                     player_pos, is_starter)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fixture_id, team_id, team_name, formation,
                    p["id"], p["name"], p["number"], p["pos"], 1
                ))

            for player in team_data.get("substitutes", []):
                p = player["player"]
                cursor.execute("""
                    INSERT INTO lineups
                    (fixture_id, team_id, team_name, formation,
                     player_id, player_name, player_number,
                     player_pos, is_starter)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    fixture_id, team_id, team_name, formation,
                    p["id"], p["name"], p["number"], p["pos"], 0
                ))

    conn.commit()
    logger.info("Lineup collection complete.")


# ---------------------------------------------------------------------------
# Export to CSV
# ---------------------------------------------------------------------------

def export_to_csv(conn: sqlite3.Connection) -> None:
    """
    Export all database tables to CSV files in data/processed/.
    These CSV files are what you will use in your analysis notebooks.

    Args:
        conn: Active SQLite connection.
    """
    os.makedirs("data/processed", exist_ok=True)
    tables = ["fixtures", "match_statistics", "match_events", "lineups"]

    for table in tables:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        path = f"data/processed/{table}.csv"
        df.to_csv(path, index=False)
        logger.info(
            "Exported %s → %s (%d rows)", table, path, len(df)
        )


# ---------------------------------------------------------------------------
# Main — runs the full pipeline when you execute this script
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orchestrate the full data collection pipeline.
    Safe to run daily — already-collected data is skipped automatically.
    """
    logger.info("=" * 55)
    logger.info("WC 2026 HB ANALYSIS — DATA COLLECTION STARTED")
    logger.info("=" * 55)

    # Connect to (or create) the database
    conn = initialise_database(DB_PATH)

    # Always refresh fixtures first — new matches complete every day
    fixture_ids = collect_fixtures(conn)

    if not fixture_ids:
        logger.error(
            "No fixtures found. "
            "Check your API key and League ID in the config section."
        )
        conn.close()
        return

    # Get only completed matches for detailed stat collection
    completed_ids = get_completed_fixture_ids(conn)
    logger.info(
        "%d total fixtures | %d completed and ready for collection",
        len(fixture_ids), len(completed_ids)
    )

    if not completed_ids:
        logger.info(
            "No completed matches yet. "
            "Run this script again after matches have been played."
        )
        conn.close()
        return

    # Collect detailed data for completed matches
    collect_match_statistics(conn, completed_ids)
    collect_match_events(conn, completed_ids)
    collect_lineups(conn, completed_ids)

    # Export everything to CSV for analysis
    export_to_csv(conn)

    conn.close()
    logger.info("=" * 55)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()