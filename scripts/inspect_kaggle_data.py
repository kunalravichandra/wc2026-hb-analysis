# scripts/inspect_kaggle_data.py
"""
Module: inspect_kaggle_data.py
Purpose: Systematically inspect every CSV file in the Kaggle
         WC 2026 dataset before using it in our analysis.
         We verify row counts, column names, data types,
         missing values, and sample records for each file.
         This is standard due diligence before trusting
         any external dataset.
Author: Kunal R
Date: 2026
Standards: PEP8
"""

import os
import pandas as pd
import sqlite3
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KAGGLE_DIR = "data/raw/kaggle"
DB_PATH = "data/raw/wc2026_raw.db"

# These are the files we expect based on the dataset description
# We check each one exists and has the right structure
EXPECTED_FILES = {
    "teams.csv": {
        "description": "48 participating countries",
        "critical_cols": ["team_id", "team_name", "group_letter"]
    },
    "venues.csv": {
        "description": "16 host stadiums with coordinates",
        "critical_cols": [
            "venue_id", "stadium_name", "city",
            "latitude", "longitude", "elevation_meters"
        ]
    },
    "tournament_stages.csv": {
        "description": "Stage lookup table",
        "critical_cols": ["stage_id", "stage_name"]
    },
    "referees.csv": {
        "description": "Match referees",
        "critical_cols": ["referee_id", "name", "country"]
    },
    "matches.csv": {
        "description": "Match outcomes with xG",
        "critical_cols": [
            "match_id", "date", "home_team_id", "away_team_id",
            "home_score", "away_score", "home_xg", "away_xg"
        ]
    },
    "matches_detailed.csv": {
        "description": "Denormalized match data with names",
        "critical_cols": [
            "match_id", "home_team_name", "away_team_name",
            "home_score", "away_score"
        ]
    },
    "match_events.csv": {
        "description": "Goals cards subs with exact minutes",
        "critical_cols": [
            "event_id", "match_id", "minute", "event_type"
        ]
    },
    "match_team_stats.csv": {
        "description": "Possession shots corners per match",
        "critical_cols": [
            "match_id", "team_id", "possession_pct",
            "total_shots", "shots_on_target"
        ]
    },
    "match_lineups.csv": {
        "description": "Starting XI and substitutes",
        "critical_cols": [
            "match_id", "player_id", "team_id",
            "is_starting_xi", "minutes_played"
        ]
    },
    "squads_and_players.csv": {
        "description": "1248 players across all squads",
        "critical_cols": [
            "player_id", "team_id", "player_name", "position"
        ]
    },
    "player_stats.csv": {
        "description": "Cumulative tournament stats per player",
        "critical_cols": [
            "player_id", "team_id", "goals", "assists"
        ]
    },
    "match_prediction_features.csv": {
        "description": "65 ML-ready features per match",
        "critical_cols": ["match_id"]
    }
}


# ---------------------------------------------------------------------------
# Inspection functions
# ---------------------------------------------------------------------------

def inspect_file(filename: str, config: dict) -> pd.DataFrame | None:
    """
    Load and inspect a single CSV file from the Kaggle dataset.
    Prints a structured report of its contents and quality.

    Args:
        filename: Name of the CSV file to inspect.
        config: Dictionary with description and critical_cols.

    Returns:
        Loaded DataFrame if successful, None if file missing.
    """
    filepath = os.path.join(KAGGLE_DIR, filename)

    print("\n" + "=" * 55)
    print(f"FILE: {filename}")
    print(f"DESC: {config['description']}")
    print("=" * 55)

    # Check file exists
    if not os.path.exists(filepath):
        print(f"MISSING — file not found at {filepath}")
        return None

    # Load the file
    try:
        df = pd.read_csv(filepath)
    except Exception as exc:
        print(f"ERROR loading file: {exc}")
        return None

    # Basic stats
    print(f"Rows         : {len(df):,}")
    print(f"Columns      : {len(df.columns)}")
    print(f"File size    : "
          f"{os.path.getsize(filepath) / 1024:.1f} KB")

    # Column list
    print(f"\nAll columns:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        nulls = df[col].isnull().sum()
        null_pct = (nulls / len(df) * 100) if len(df) > 0 else 0
        null_str = f"{nulls} nulls ({null_pct:.0f}%)" if nulls > 0 else "complete"
        print(f"  {col:<40} {dtype:<12} {null_str}")

    # Check critical columns
    print(f"\nCritical column check:")
    for col in config["critical_cols"]:
        if col in df.columns:
            print(f"  ✓ {col}")
        else:
            print(f"  ✗ {col} — MISSING")

    # Sample data
    print(f"\nFirst 3 rows:")
    pd.set_option("display.max_columns", 6)
    pd.set_option("display.width", 100)
    print(df.head(3).to_string(index=False))

    return df


def check_match_events_detail(df: pd.DataFrame) -> None:
    """
    Deep inspection of match_events.csv since this is our
    most critical file for HB window analysis.
    We need to confirm minute granularity and event type coverage.

    Args:
        df: The match_events DataFrame.
    """
    print("\n" + "=" * 55)
    print("DEEP INSPECTION — MATCH EVENTS")
    print("(Critical file for HB window analysis)")
    print("=" * 55)

    if "event_type" in df.columns:
        print("Event types and counts:")
        event_counts = df["event_type"].value_counts()
        for event_type, count in event_counts.items():
            print(f"  {event_type:<30} {count:>6}")

    if "minute" in df.columns:
        print(f"\nMinute field stats:")
        print(f"  Min minute  : {df['minute'].min()}")
        print(f"  Max minute  : {df['minute'].max()}")
        print(f"  Null minutes: {df['minute'].isnull().sum()}")

        # Check if we have substitution timing data
        if "event_type" in df.columns:
            subs = df[df["event_type"].str.lower().str.contains(
                "sub", na=False
            )]
            print(f"\nSubstitution events: {len(subs)}")
            if len(subs) > 0:
                print("Sample substitutions with minutes:")
                print(subs[["match_id", "minute",
                             "event_type"]].head(5).to_string(
                    index=False
                ))

            # Check for goals with minutes
            goals = df[df["event_type"].str.lower().str.contains(
                "goal", na=False
            )]
            print(f"\nGoal events: {len(goals)}")
            if len(goals) > 0:
                print("Sample goals with minutes:")
                print(goals[["match_id", "minute",
                              "event_type"]].head(5).to_string(
                    index=False
                ))


def check_match_stats_detail(df: pd.DataFrame) -> None:
    """
    Deep inspection of match_team_stats.csv to verify
    possession and shot data completeness across all matches.

    Args:
        df: The match_team_stats DataFrame.
    """
    print("\n" + "=" * 55)
    print("DEEP INSPECTION — MATCH TEAM STATS")
    print("(Core metrics for pre/post HB comparison)")
    print("=" * 55)

    if "possession_pct" in df.columns:
        non_null = df["possession_pct"].notnull().sum()
        total = len(df)
        print(f"Possession data: {non_null}/{total} rows populated "
              f"({non_null/total*100:.0f}%)")
        if non_null > 0:
            print(f"  Range: {df['possession_pct'].min():.1f}% "
                  f"to {df['possession_pct'].max():.1f}%")

    if "total_shots" in df.columns:
        non_null = df["total_shots"].notnull().sum()
        print(f"Shots data     : {non_null}/{len(df)} rows populated")

    if "shots_on_target" in df.columns:
        non_null = df["shots_on_target"].notnull().sum()
        print(f"SOT data       : {non_null}/{len(df)} rows populated")

    if "data_source" in df.columns:
        print(f"\nData sources used:")
        for source, count in df["data_source"].value_counts().items():
            print(f"  {source:<30} {count} rows")


def check_venues_detail(df: pd.DataFrame) -> None:
    """
    Deep inspection of venues.csv to confirm we have
    coordinates and elevation for weather data enrichment.

    Args:
        df: The venues DataFrame.
    """
    print("\n" + "=" * 55)
    print("DEEP INSPECTION — VENUES")
    print("(Needed for Open-Meteo weather API calls)")
    print("=" * 55)

    coord_cols = ["latitude", "longitude", "elevation_meters"]
    for col in coord_cols:
        if col in df.columns:
            nulls = df[col].isnull().sum()
            print(f"{col}: {nulls} nulls out of {len(df)} venues")

    if all(c in df.columns for c in ["stadium_name", "city", "country"]):
        print(f"\nAll venues:")
        for _, row in df.iterrows():
            lat = row.get("latitude", "?")
            lon = row.get("longitude", "?")
            elev = row.get("elevation_meters", "?")
            print(f"  {row['stadium_name']:<35} "
                  f"{row['city']:<20} "
                  f"lat:{lat} lon:{lon} elev:{elev}m")


def check_matches_xg(df: pd.DataFrame) -> None:
    """
    Verify xG data completeness in matches.csv.
    xG is one of our primary analytical metrics.

    Args:
        df: The matches DataFrame.
    """
    print("\n" + "=" * 55)
    print("DEEP INSPECTION — xG IN MATCHES")
    print("(Expected goals — key metric for H1 and H3)")
    print("=" * 55)

    for col in ["home_xg", "away_xg"]:
        if col in df.columns:
            non_null = df[col].notnull().sum()
            total = len(df)
            print(f"{col}: {non_null}/{total} populated "
                  f"({non_null/total*100:.0f}%)")
            if non_null > 0:
                print(f"  Range: {df[col].min():.2f} "
                      f"to {df[col].max():.2f}")

    # Check finished matches specifically
    if "status" in df.columns:
        finished = df[df["status"].str.upper() == "FINISHED"]
        print(f"\nFinished matches: {len(finished)}")
        if "home_xg" in df.columns:
            xg_populated = finished["home_xg"].notnull().sum()
            print(f"xG populated for finished: "
                  f"{xg_populated}/{len(finished)}")


def check_prediction_features(df: pd.DataFrame) -> None:
    """
    Quick scan of the ML features file to understand
    what pre-calculated features are available.

    Args:
        df: The match_prediction_features DataFrame.
    """
    print("\n" + "=" * 55)
    print("DEEP INSPECTION — ML PREDICTION FEATURES")
    print(f"({len(df.columns)} pre-calculated features)")
    print("=" * 55)

    # Group columns by category based on naming patterns
    categories = {
        "Team ratings": [
            c for c in df.columns
            if any(x in c.lower() for x in ["elo", "ranking", "value"])
        ],
        "Rolling form": [
            c for c in df.columns
            if any(x in c.lower() for x in ["rolling", "form", "avg"])
        ],
        "Environmental": [
            c for c in df.columns
            if any(x in c.lower() for x in
                   ["elevation", "temperature", "humidity"])
        ],
        "Fatigue": [
            c for c in df.columns
            if any(x in c.lower() for x in ["rest", "fatigue", "days"])
        ],
        "Target labels": [
            c for c in df.columns
            if any(x in c.lower() for x in
                   ["result", "winner", "outcome", "target"])
        ]
    }

    for category, cols in categories.items():
        if cols:
            print(f"\n{category} ({len(cols)} features):")
            for col in cols[:8]:
                print(f"  {col}")
            if len(cols) > 8:
                print(f"  ... and {len(cols) - 8} more")

    # Show all columns not caught by categories
    categorised = [c for cols in categories.values() for c in cols]
    uncategorised = [
        c for c in df.columns if c not in categorised
    ]
    if uncategorised:
        print(f"\nOther features ({len(uncategorised)}):")
        for col in uncategorised[:15]:
            print(f"  {col}")
        if len(uncategorised) > 15:
            print(f"  ... and {len(uncategorised) - 15} more")


# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------

def load_into_database(dataframes: dict) -> None:
    """
    Load all successfully inspected DataFrames into our
    SQLite database alongside the football-data.org data
    we already collected. Uses table names prefixed with
    'kaggle_' to avoid conflicts with existing tables.

    Args:
        dataframes: Dictionary of filename to DataFrame.
    """
    print("\n" + "=" * 55)
    print("LOADING INTO SQLITE DATABASE")
    print("=" * 55)

    conn = sqlite3.connect(DB_PATH)

    # Map filename to clean table name
    table_map = {
        "teams.csv": "kaggle_teams",
        "venues.csv": "kaggle_venues",
        "tournament_stages.csv": "kaggle_stages",
        "referees.csv": "kaggle_referees",
        "matches.csv": "kaggle_matches",
        "matches_detailed.csv": "kaggle_matches_detailed",
        "match_events.csv": "kaggle_match_events",
        "match_team_stats.csv": "kaggle_match_team_stats",
        "match_lineups.csv": "kaggle_match_lineups",
        "squads_and_players.csv": "kaggle_players",
        "player_stats.csv": "kaggle_player_stats",
        "match_prediction_features.csv": "kaggle_ml_features"
    }

    for filename, df in dataframes.items():
        table_name = table_map.get(filename)
        if not table_name:
            continue

        try:
            df.to_sql(
                table_name,
                conn,
                if_exists="replace",
                index=False
            )
            print(f"  Loaded {filename:<45} "
                  f"→ {table_name} ({len(df)} rows)")
        except Exception as exc:
            print(f"  ERROR loading {filename}: {exc}")

    conn.close()
    print("\nAll tables loaded into database successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Inspect all Kaggle WC 2026 CSV files and load into database.
    Run this once after downloading and extracting the dataset.
    """
    print("=" * 55)
    print("KAGGLE WC 2026 DATASET INSPECTION")
    print("=" * 55)
    print(f"Looking for files in: {KAGGLE_DIR}")
    print(f"Database target     : {DB_PATH}")

    # Check the directory exists and has files
    if not os.path.exists(KAGGLE_DIR):
        print(f"\nERROR: Directory not found: {KAGGLE_DIR}")
        print("Create it and copy your Kaggle CSV files into it:")
        print(f"  mkdir {KAGGLE_DIR}")
        return

    found_files = [
        f for f in os.listdir(KAGGLE_DIR)
        if f.endswith(".csv")
    ]
    print(f"CSV files found     : {len(found_files)}")
    for f in sorted(found_files):
        size = os.path.getsize(
            os.path.join(KAGGLE_DIR, f)
        ) / 1024
        print(f"  {f:<45} {size:.1f} KB")

    # Inspect each expected file
    dataframes = {}
    for filename, config in EXPECTED_FILES.items():
        df = inspect_file(filename, config)
        if df is not None:
            dataframes[filename] = df

    # Deep inspections for critical files
    if "match_events.csv" in dataframes:
        check_match_events_detail(dataframes["match_events.csv"])

    if "match_team_stats.csv" in dataframes:
        check_match_stats_detail(dataframes["match_team_stats.csv"])

    if "venues.csv" in dataframes:
        check_venues_detail(dataframes["venues.csv"])

    if "matches.csv" in dataframes:
        check_matches_xg(dataframes["matches.csv"])

    if "match_prediction_features.csv" in dataframes:
        check_prediction_features(
            dataframes["match_prediction_features.csv"]
        )

    # Load everything into database
    if dataframes:
        load_into_database(dataframes)

    # Final summary
    print("\n" + "=" * 55)
    print("INSPECTION COMPLETE")
    print("=" * 55)
    print(f"Files successfully loaded : {len(dataframes)}")
    print(f"Files missing or failed   : "
          f"{len(EXPECTED_FILES) - len(dataframes)}")

    if len(dataframes) == len(EXPECTED_FILES):
        print("\nAll files present and loaded.")
        print("Ready to proceed to feature engineering.")
    else:
        missing = [
            f for f in EXPECTED_FILES
            if f not in dataframes
        ]
        print(f"\nMissing files: {missing}")
        print("Download the complete dataset from Kaggle and retry.")


if __name__ == "__main__":
    main()