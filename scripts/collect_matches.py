# scripts/collect_matches.py
"""
Module: collect_matches.py
Purpose: Collect all FIFA World Cup 2026 match data from
         football-data.org and store in SQLite database.
         This forms the backbone dataset that all other
         sources (FBref, weather, HB log) will join onto
         using match ID as the common key.
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
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEY = os.getenv("FOOTBALL_DATA_KEY")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": KEY}
DB_PATH = "data/raw/wc2026_raw.db"
LOG_PATH = "logs/collect_matches.log"
REQUEST_DELAY = 1.0

# ---------------------------------------------------------------------------
# Venue lookup table — built from official FIFA 2026 schedule
# football-data.org returns null for venue so we map it ourselves
# This is more reliable than an API field as it never changes
# ---------------------------------------------------------------------------

VENUE_LOOKUP = {
    # Group stage venues mapped by city
    # Source: FIFA official match schedule
    "New York/New Jersey": {
        "venue": "MetLife Stadium",
        "city": "East Rutherford",
        "state": "New Jersey",
        "country": "USA",
        "latitude": 40.8135,
        "longitude": -74.0745,
        "timezone": "America/New_York",
        "has_ac": True,
        "capacity": 82500
    },
    "Los Angeles": {
        "venue": "SoFi Stadium",
        "city": "Inglewood",
        "state": "California",
        "country": "USA",
        "latitude": 33.9535,
        "longitude": -118.3392,
        "timezone": "America/Los_Angeles",
        "has_ac": True,
        "capacity": 70240
    },
    "Dallas": {
        "venue": "AT&T Stadium",
        "city": "Arlington",
        "state": "Texas",
        "country": "USA",
        "latitude": 32.7473,
        "longitude": -97.0945,
        "timezone": "America/Chicago",
        "has_ac": True,
        "capacity": 80000
    },
    "San Francisco Bay Area": {
        "venue": "Levi's Stadium",
        "city": "Santa Clara",
        "state": "California",
        "country": "USA",
        "latitude": 37.4033,
        "longitude": -121.9694,
        "timezone": "America/Los_Angeles",
        "has_ac": False,
        "capacity": 68500
    },
    "Miami": {
        "venue": "Hard Rock Stadium",
        "city": "Miami Gardens",
        "state": "Florida",
        "country": "USA",
        "latitude": 25.9580,
        "longitude": -80.2389,
        "timezone": "America/New_York",
        "has_ac": False,
        "capacity": 65326
    },
    "Kansas City": {
        "venue": "Arrowhead Stadium",
        "city": "Kansas City",
        "state": "Missouri",
        "country": "USA",
        "latitude": 39.0489,
        "longitude": -94.4839,
        "timezone": "America/Chicago",
        "has_ac": False,
        "capacity": 76416
    },
    "Philadelphia": {
        "venue": "Lincoln Financial Field",
        "city": "Philadelphia",
        "state": "Pennsylvania",
        "country": "USA",
        "latitude": 39.9008,
        "longitude": -75.1675,
        "timezone": "America/New_York",
        "has_ac": False,
        "capacity": 69596
    },
    "Boston": {
        "venue": "Gillette Stadium",
        "city": "Foxborough",
        "state": "Massachusetts",
        "country": "USA",
        "latitude": 42.0909,
        "longitude": -71.2643,
        "timezone": "America/New_York",
        "has_ac": False,
        "capacity": 65878
    },
    "Houston": {
        "venue": "NRG Stadium",
        "city": "Houston",
        "state": "Texas",
        "country": "USA",
        "latitude": 29.6847,
        "longitude": -95.4107,
        "timezone": "America/Chicago",
        "has_ac": True,
        "capacity": 72220
    },
    "Seattle": {
        "venue": "Lumen Field",
        "city": "Seattle",
        "state": "Washington",
        "country": "USA",
        "latitude": 47.5952,
        "longitude": -122.3316,
        "timezone": "America/Los_Angeles",
        "has_ac": False,
        "capacity": 68740
    },
    "Atlanta": {
        "venue": "Mercedes-Benz Stadium",
        "city": "Atlanta",
        "state": "Georgia",
        "country": "USA",
        "latitude": 33.7553,
        "longitude": -84.4006,
        "timezone": "America/New_York",
        "has_ac": True,
        "capacity": 71000
    },
    "Mexico City": {
        "venue": "Estadio Azteca",
        "city": "Mexico City",
        "state": "Mexico City",
        "country": "Mexico",
        "latitude": 19.3029,
        "longitude": -99.1505,
        "timezone": "America/Mexico_City",
        "has_ac": False,
        "capacity": 87523
    },
    "Guadalajara": {
        "venue": "Estadio Akron",
        "city": "Zapopan",
        "state": "Jalisco",
        "country": "Mexico",
        "latitude": 20.6869,
        "longitude": -103.4663,
        "timezone": "America/Mexico_City",
        "has_ac": False,
        "capacity": 49850
    },
    "Monterrey": {
        "venue": "Estadio BBVA",
        "city": "Monterrey",
        "state": "Nuevo Leon",
        "country": "Mexico",
        "latitude": 25.6694,
        "longitude": -100.2436,
        "timezone": "America/Mexico_City",
        "has_ac": False,
        "capacity": 53500
    },
    "Vancouver": {
        "venue": "BC Place",
        "city": "Vancouver",
        "state": "British Columbia",
        "country": "Canada",
        "latitude": 49.2767,
        "longitude": -123.1117,
        "timezone": "America/Vancouver",
        "has_ac": False,
        "capacity": 54500
    },
    "Toronto": {
        "venue": "BMO Field",
        "city": "Toronto",
        "state": "Ontario",
        "country": "Canada",
        "latitude": 43.6332,
        "longitude": -79.4189,
        "timezone": "America/Toronto",
        "has_ac": False,
        "capacity": 30000
    }
}

# ---------------------------------------------------------------------------
# Logging setup
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
    Create SQLite database and all required tables.
    Safe to run multiple times — tables created only once.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active SQLite connection object.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id            INTEGER PRIMARY KEY,
            utc_date            TEXT,
            status              TEXT,
            matchday            INTEGER,
            stage               TEXT,
            group_name          TEXT,
            home_team_id        INTEGER,
            home_team_name      TEXT,
            home_team_code      TEXT,
            away_team_id        INTEGER,
            away_team_name      TEXT,
            away_team_code      TEXT,
            score_home_ft       INTEGER,
            score_away_ft       INTEGER,
            score_home_ht       INTEGER,
            score_away_ht       INTEGER,
            winner              TEXT,
            duration            TEXT,
            referee_name        TEXT,
            referee_nationality TEXT,
            venue_name          TEXT,
            venue_city          TEXT,
            venue_country       TEXT,
            venue_has_ac        INTEGER,
            venue_latitude      REAL,
            venue_longitude     REAL,
            venue_timezone      TEXT,
            collected_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS teams (
            team_id             INTEGER PRIMARY KEY,
            team_name           TEXT,
            team_short_name     TEXT,
            team_code           TEXT,
            collected_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS standings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name          TEXT,
            team_id             INTEGER,
            team_name           TEXT,
            position            INTEGER,
            played              INTEGER,
            won                 INTEGER,
            drawn               INTEGER,
            lost                INTEGER,
            goals_for           INTEGER,
            goals_against       INTEGER,
            goal_difference     INTEGER,
            points              INTEGER,
            collected_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS scorers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id           INTEGER,
            player_name         TEXT,
            team_id             INTEGER,
            team_name           TEXT,
            played_matches      INTEGER,
            goals               INTEGER,
            assists             INTEGER,
            penalties           INTEGER,
            collected_at        TEXT
        );
    """)

    conn.commit()
    logger.info("Database ready at: %s", db_path)
    return conn


# ---------------------------------------------------------------------------
# API request handler
# ---------------------------------------------------------------------------

def make_request(endpoint: str, params: dict = None) -> dict | None:
    """
    Make a single GET request to football-data.org.
    Handles errors gracefully and respects rate limits.

    Args:
        endpoint: API endpoint path e.g. '/competitions/WC/matches'
        params: Optional query parameters as a dictionary.

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

        if response.status_code == 429:
            logger.warning("Rate limit hit — waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=10
            )

        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return response.json()

    except requests.exceptions.RequestException as exc:
        logger.error("Request failed for %s: %s", endpoint, exc)
        return None


# ---------------------------------------------------------------------------
# Venue resolver
# ---------------------------------------------------------------------------

def resolve_venue(home_team: str, away_team: str,
                  utc_date: str) -> dict:
    """
    Resolve venue information for a match.
    football-data.org returns null for venue so we use a combination
    of our lookup table and match date to assign the correct stadium.

    Since we cannot reliably map every match to a city automatically
    without the official FIFA city-by-match schedule, this function
    returns a default structure that we will populate manually
    for key matches, or enrich later from FBref scraping.

    Args:
        home_team: Home team name.
        away_team: Away team name.
        utc_date: Match UTC date string.

    Returns:
        Dictionary with venue fields, defaulting to None if unknown.
    """
    return {
        "venue_name": None,
        "venue_city": None,
        "venue_country": None,
        "venue_has_ac": None,
        "venue_latitude": None,
        "venue_longitude": None,
        "venue_timezone": None
    }


# ---------------------------------------------------------------------------
# Collection functions
# ---------------------------------------------------------------------------

def collect_matches(conn: sqlite3.Connection) -> list:
    """
    Fetch all WC 2026 matches and store in the matches table.
    Includes both finished and upcoming matches — status field
    tells us which is which.

    Args:
        conn: Active SQLite connection.

    Returns:
        List of all match IDs collected.
    """
    logger.info("Collecting all WC 2026 matches...")

    data = make_request("/competitions/WC/matches")

    if not data:
        logger.error("Failed to fetch matches.")
        return []

    matches = data.get("matches", [])
    cursor = conn.cursor()
    match_ids = []

    for match in matches:
        score = match.get("score", {})
        ft = score.get("fullTime", {})
        ht = score.get("halfTime", {})
        referees = match.get("referees", [])
        referee = referees[0] if referees else {}
        venue_info = resolve_venue(
            match["homeTeam"]["name"],
            match["awayTeam"]["name"],
            match["utcDate"]
        )

        cursor.execute("""
            INSERT OR REPLACE INTO matches VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match["id"],
            match["utcDate"],
            match["status"],
            match.get("matchday"),
            match.get("stage"),
            match.get("group"),
            match["homeTeam"]["id"],
            match["homeTeam"]["name"],
            match["homeTeam"].get("tla"),
            match["awayTeam"]["id"],
            match["awayTeam"]["name"],
            match["awayTeam"].get("tla"),
            ft.get("home"),
            ft.get("away"),
            ht.get("home"),
            ht.get("away"),
            score.get("winner"),
            score.get("duration"),
            referee.get("name"),
            referee.get("nationality"),
            venue_info["venue_name"],
            venue_info["venue_city"],
            venue_info["venue_country"],
            venue_info["venue_has_ac"],
            venue_info["venue_latitude"],
            venue_info["venue_longitude"],
            venue_info["venue_timezone"],
            datetime.now(timezone.utc).isoformat()
        ))

        match_ids.append(match["id"])

    conn.commit()
    logger.info("Collected %d matches.", len(match_ids))
    return match_ids


def collect_teams(conn: sqlite3.Connection) -> None:
    """
    Fetch all 48 teams in WC 2026 and store in teams table.

    Args:
        conn: Active SQLite connection.
    """
    logger.info("Collecting teams...")

    data = make_request("/competitions/WC/teams")

    if not data:
        logger.error("Failed to fetch teams.")
        return

    teams = data.get("teams", [])
    cursor = conn.cursor()

    for team in teams:
        cursor.execute("""
            INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?, ?)
        """, (
            team["id"],
            team["name"],
            team.get("shortName"),
            team.get("tla"),
            datetime.now(timezone.utc).isoformat()
        ))

    conn.commit()
    logger.info("Collected %d teams.", len(teams))


def collect_standings(conn: sqlite3.Connection) -> None:
    """
    Fetch group stage standings for all 12 groups.
    Standings give us context about how much each team needed
    points at the time of each match — relevant for tactical
    desperation analysis around HBs.

    Args:
        conn: Active SQLite connection.
    """
    logger.info("Collecting standings...")

    data = make_request("/competitions/WC/standings")

    if not data:
        logger.error("Failed to fetch standings.")
        return

    standings = data.get("standings", [])
    cursor = conn.cursor()

    # Clear existing standings — these update as matches complete
    cursor.execute("DELETE FROM standings")

    for group in standings:
        group_name = group.get("group", "UNKNOWN")

        for entry in group.get("table", []):
            cursor.execute("""
                INSERT INTO standings VALUES
                (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                group_name,
                entry["team"]["id"],
                entry["team"]["name"],
                entry["position"],
                entry["playedGames"],
                entry["won"],
                entry["draw"],
                entry["lost"],
                entry["goalsFor"],
                entry["goalsAgainst"],
                entry["goalDifference"],
                entry["points"],
                datetime.now(timezone.utc).isoformat()
            ))

    conn.commit()
    logger.info("Standings collected for %d groups.", len(standings))


def collect_scorers(conn: sqlite3.Connection) -> None:
    """
    Fetch top scorers for WC 2026.
    Useful context for identifying key players to watch
    around HB windows in individual match analysis.

    Args:
        conn: Active SQLite connection.
    """
    logger.info("Collecting top scorers...")

    data = make_request(
        "/competitions/WC/scorers",
        params={"limit": 50}
    )

    if not data:
        logger.error("Failed to fetch scorers.")
        return

    scorers = data.get("scorers", [])
    cursor = conn.cursor()

    # Clear and refresh — scorer totals update after every match
    cursor.execute("DELETE FROM scorers")

    for entry in scorers:
        player = entry.get("player", {})
        team = entry.get("team", {})

        cursor.execute("""
            INSERT INTO scorers VALUES
            (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player.get("id"),
            player.get("name"),
            team.get("id"),
            team.get("name"),
            entry.get("playedMatches"),
            entry.get("goals"),
            entry.get("assists"),
            entry.get("penalties"),
            datetime.now(timezone.utc).isoformat()
        ))

    conn.commit()
    logger.info("Collected %d scorer records.", len(scorers))


# ---------------------------------------------------------------------------
# Export to CSV
# ---------------------------------------------------------------------------

def export_to_csv(conn: sqlite3.Connection) -> None:
    """
    Export all tables to CSV files in data/processed/.
    These are the files you will load in your analysis notebooks.

    Args:
        conn: Active SQLite connection.
    """
    os.makedirs("data/processed", exist_ok=True)

    tables = ["matches", "teams", "standings", "scorers"]

    for table in tables:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        path = f"data/processed/{table}.csv"
        df.to_csv(path, index=False)
        logger.info(
            "Exported %s -> %s (%d rows)",
            table, path, len(df)
        )


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def print_summary(conn: sqlite3.Connection) -> None:
    """
    Print a human readable summary of what was collected.
    Gives you a quick sanity check without opening any files.

    Args:
        conn: Active SQLite connection.
    """
    print("\n" + "=" * 55)
    print("COLLECTION SUMMARY")
    print("=" * 55)

    queries = {
        "Total matches": "SELECT COUNT(*) FROM matches",
        "Finished matches": (
            "SELECT COUNT(*) FROM matches WHERE status = 'FINISHED'"
        ),
        "Upcoming matches": (
            "SELECT COUNT(*) FROM matches WHERE status = 'TIMED'"
        ),
        "Group stage matches": (
            "SELECT COUNT(*) FROM matches WHERE stage = 'GROUP_STAGE'"
        ),
        "Knockout matches": (
            "SELECT COUNT(*) FROM matches WHERE stage != 'GROUP_STAGE'"
        ),
        "Teams": "SELECT COUNT(*) FROM teams",
        "Groups in standings": (
            "SELECT COUNT(DISTINCT group_name) FROM standings"
        ),
        "Scorers tracked": "SELECT COUNT(*) FROM scorers"
    }

    for label, query in queries.items():
        count = pd.read_sql_query(query, conn).iloc[0, 0]
        print(f"  {label:<30} {int(count):>6}")

    print("\nFinished matches by stage:")
    stage_df = pd.read_sql_query("""
        SELECT stage, COUNT(*) as count
        FROM matches
        WHERE status = 'FINISHED'
        GROUP BY stage
        ORDER BY count DESC
    """, conn)

    for _, row in stage_df.iterrows():
        print(f"  {row['stage']:<30} {int(row['count']):>6}")

    print("\nSample of finished matches:")
    sample_df = pd.read_sql_query("""
        SELECT
            home_team_name,
            score_home_ft,
            score_away_ft,
            away_team_name,
            group_name,
            stage
        FROM matches
        WHERE status = 'FINISHED'
        ORDER BY utc_date
        LIMIT 8
    """, conn)

    for _, row in sample_df.iterrows():
        print(
            f"  {row['home_team_name']:<22} "
            f"{int(row['score_home_ft'])} - "
            f"{int(row['score_away_ft'])}"
            f"  {row['away_team_name']:<22} "
            f"  {row['group_name'] or row['stage']}"
        )

    print("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run the full collection pipeline.
    Safe to run daily — matches use INSERT OR REPLACE,
    standings and scorers are cleared and refreshed each run.
    """
    logger.info("=" * 55)
    logger.info("WC 2026 — MATCH DATA COLLECTION STARTED")
    logger.info("=" * 55)

    conn = initialise_database(DB_PATH)

    collect_matches(conn)
    collect_teams(conn)
    collect_standings(conn)
    collect_scorers(conn)
    export_to_csv(conn)
    print_summary(conn)

    conn.close()

    logger.info("=" * 55)
    logger.info("COLLECTION COMPLETE")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()