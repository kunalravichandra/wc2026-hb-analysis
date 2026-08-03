# scripts/load_hb_data.py
"""
Module: load_hb_data.py
Purpose: Load verified hydration break timing data from
         Dey (2026) into our SQLite database.

         Source: Dey, D. (2026). Do In-Match Hydration Breaks
         Alter Match Momentum? A Within-Match Case-Crossover
         Analysis of the 2026 FIFA World Cup.
         arXiv:2607.19783. https://github.com/Ddey07/
         wc2026-hydration-momentum

         This file covers 32 knockout phase matches with
         exact HB minutes read from live commentary.
         Group stage data requires separate collection.

Author: Your Name
Date: 2026
Standards: PEP8
"""

import json
import sqlite3
import pandas as pd
import os
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = "data/raw/wc2026_raw.db"
HB_JSON_PATH = "data/raw/kaggle/break_times_exact.json"
OUTPUT_CSV = "data/processed/hb_times_knockout.csv"


# ---------------------------------------------------------------------------
# Load and parse
# ---------------------------------------------------------------------------

def load_hb_json(path: str) -> list:
    """
    Load the break_times_exact.json file from Dey (2026).

    Args:
        path: Path to the JSON file.

    Returns:
        List of match dictionaries with break timing data.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"HB data file not found at {path}. "
            "Please place break_times_exact.json in data/raw/kaggle/"
        )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} match records from {path}")
    return data


def parse_hb_records(raw: list) -> pd.DataFrame:
    """
    Parse the raw JSON into a structured DataFrame with one
    row per hydration break per match (two rows per match).

    The breakMins field contains [HB1_minute, HB2_minute].
    We split these into separate rows for easier analysis.

    Args:
        raw: List of raw match dictionaries from JSON.

    Returns:
        DataFrame with one HB event per row.
    """
    records = []

    for match in raw:
        match_id_dey = match["id"]
        round_name = match["round"]
        home = match["home"]
        away = match["away"]
        break_mins = match.get("breakMins", [])
        n_commentary = match.get("nCom", None)

        if len(break_mins) >= 1:
            records.append({
                "dey_match_id":       match_id_dey,
                "round":              round_name,
                "home_team":          home,
                "away_team":          away,
                "hb_number":          1,
                "half":               1,
                "hb_actual_minute":   break_mins[0],
                "deviation_from_22":  break_mins[0] - 22,
                "n_commentary_events": n_commentary,
                "data_source":        "Dey (2026) arXiv:2607.19783",
                "collection_method":  "Live text commentary",
                "manually_verified":  1,
                "loaded_at": datetime.now(timezone.utc).isoformat()
            })

        if len(break_mins) >= 2:
            records.append({
                "dey_match_id":       match_id_dey,
                "round":              round_name,
                "home_team":          home,
                "away_team":          away,
                "hb_number":          2,
                "half":               2,
                "hb_actual_minute":   break_mins[1],
                "deviation_from_67":  break_mins[1] - 67,
                "n_commentary_events": n_commentary,
                "data_source":        "Dey (2026) arXiv:2607.19783",
                "collection_method":  "Live text commentary",
                "manually_verified":  1,
                "loaded_at": datetime.now(timezone.utc).isoformat()
            })

    df = pd.DataFrame(records)
    return df


def analyse_timing_distribution(df: pd.DataFrame) -> None:
    """
    Print statistical summary of actual HB timing distribution.
    This is directly useful for the methodology section of our paper.
    It shows how much referee discretion varied in practice.

    Args:
        df: Parsed HB records DataFrame.
    """
    print("\n" + "=" * 55)
    print("HB TIMING ANALYSIS — KNOCKOUT PHASE")
    print("(32 matches, source: Dey 2026 arXiv:2607.19783)")
    print("=" * 55)

    for hb_num in [1, 2]:
        half_df = df[df["hb_number"] == hb_num]
        target = 22 if hb_num == 1 else 67
        label = f"HB{hb_num} (target: {target}')"

        print(f"\n{label}:")
        print(f"  Matches       : {len(half_df)}")
        print(f"  Min minute    : {half_df['hb_actual_minute'].min()}")
        print(f"  Max minute    : {half_df['hb_actual_minute'].max()}")
        print(f"  Mean minute   : "
              f"{half_df['hb_actual_minute'].mean():.1f}")
        print(f"  Std deviation : "
              f"{half_df['hb_actual_minute'].std():.1f}")

        # Distribution
        print(f"  Distribution  :")
        counts = half_df["hb_actual_minute"].value_counts().sort_index()
        for minute, count in counts.items():
            bar = "█" * count
            print(f"    Min {minute:>2}: {bar} ({count})")

        # Outliers — more than 3 minutes from target
        dev_col = "deviation_from_22" if hb_num == 1 else "deviation_from_67"
        if dev_col in half_df.columns:
            outliers = half_df[
                abs(half_df[dev_col]) > 3
            ][["home_team", "away_team", "hb_actual_minute", dev_col]]
            if len(outliers) > 0:
                print(f"  Outliers (>{target}+3):")
                for _, row in outliers.iterrows():
                    print(f"    {row['home_team']} vs "
                          f"{row['away_team']}: "
                          f"minute {row['hb_actual_minute']} "
                          f"(+{row[dev_col]})")


def match_to_kaggle_ids(df: pd.DataFrame,
                         conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Attempt to match Dey's match records to our Kaggle match IDs
    using home team and away team names.

    This is necessary because Dey uses his own match IDs while
    our database uses Kaggle's match IDs. We join on team names.

    Note: Team name mismatches are possible — Dey may use
    different name variants (e.g. 'USA' vs 'United States').
    Unmatched records are flagged for manual resolution.

    Args:
        df: Parsed HB records DataFrame.
        conn: Active SQLite connection.

    Returns:
        DataFrame with kaggle_match_id column added where matched.
    """
    kaggle_matches = pd.read_sql_query("""
        SELECT
            m.match_id as kaggle_match_id,
            t1.team_name as home_name,
            t2.team_name as away_name,
            m.date
        FROM kaggle_matches m
        JOIN kaggle_teams t1 ON m.home_team_id = t1.team_id
        JOIN kaggle_teams t2 ON m.away_team_id = t2.team_id
    """, conn)

    # Get unique matches from HB data (one row per match not per HB)
    hb_matches = df.drop_duplicates("dey_match_id")[
        ["dey_match_id", "home_team", "away_team"]
    ].copy()

    # Attempt join on team names
    merged = hb_matches.merge(
        kaggle_matches,
        left_on=["home_team", "away_team"],
        right_on=["home_name", "away_name"],
        how="left"
    )

    matched = merged["kaggle_match_id"].notnull().sum()
    unmatched = merged["kaggle_match_id"].isnull().sum()

    print(f"\n" + "=" * 55)
    print("KAGGLE ID MATCHING")
    print("=" * 55)
    print(f"  Total matches in HB data  : {len(hb_matches)}")
    print(f"  Matched to Kaggle IDs     : {matched}")
    print(f"  Unmatched (name variant)  : {unmatched}")

    if unmatched > 0:
        print("\n  Unmatched matches (need manual name fix):")
        for _, row in merged[
            merged["kaggle_match_id"].isnull()
        ].iterrows():
            print(f"    {row['home_team']} vs {row['away_team']}")

    # Merge kaggle_match_id back onto full HB dataframe
    id_map = merged[["dey_match_id", "kaggle_match_id"]]
    df = df.merge(id_map, on="dey_match_id", how="left")

    return df


def save_results(df: pd.DataFrame,
                 conn: sqlite3.Connection) -> None:
    """
    Save HB timing data to SQLite and CSV.

    Args:
        df: Complete HB records DataFrame.
        conn: Active SQLite connection.
    """
    os.makedirs("data/processed", exist_ok=True)

    df.to_sql(
        "hb_times_knockout",
        conn,
        if_exists="replace",
        index=False
    )
    print(f"\nSaved {len(df)} rows to hb_times_knockout table.")

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved to {OUTPUT_CSV}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Load, parse, analyse, and store hydration break timing data
    from Dey (2026) for the 32 knockout phase matches.
    """
    print("=" * 55)
    print("LOADING HB TIMING DATA — DEY (2026)")
    print("arXiv:2607.19783")
    print("=" * 55)

    # Load JSON
    raw = load_hb_json(HB_JSON_PATH)

    # Parse into structured format
    df = parse_hb_records(raw)
    print(f"\nParsed {len(df)} HB records "
          f"({len(df)//2} matches x 2 breaks)")

    # Analyse timing distribution
    analyse_timing_distribution(df)

    # Match to Kaggle IDs
    conn = sqlite3.connect(DB_PATH)
    df = match_to_kaggle_ids(df, conn)

    # Save
    save_results(df, conn)
    conn.close()

    print("\n" + "=" * 55)
    print("NEXT STEP: Collect group stage HB times")
    print("72 group stage matches still need HB minutes")
    print("Source: BBC Sport / ESPN live commentary archives")
    print("=" * 55)


if __name__ == "__main__":
    main()