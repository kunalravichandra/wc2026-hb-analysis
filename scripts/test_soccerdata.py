# scripts/test_soccerdata.py
"""
Module: test_soccerdata.py
Purpose: Test the soccerdata library for WC 2026 data access.
         soccerdata is a Python wrapper that extracts data from
         multiple football analytics platforms including FBref,
         Understat, and others into clean pandas DataFrames.
         
         Important context: FBref lost its Opta data license in
         January 2026. This test checks what data remains available
         for WC 2026 specifically despite that change.
Author: Your Name
Date: 2026
Standards: PEP8
"""

import warnings
import sys

# Suppress verbose library warnings during testing
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Test 1 — Verify library installed correctly
# ---------------------------------------------------------------------------

def test_import() -> bool:
    """
    Verify soccerdata installed and imports correctly.

    Returns:
        True if import successful, False otherwise.
    """
    print("=" * 55)
    print("TEST 1 — LIBRARY IMPORT")
    print("=" * 55)

    try:
        import soccerdata as sd
        print(f"soccerdata imported successfully")
        print(f"Version: {sd.__version__}")
        return True

    except ImportError as exc:
        print(f"Import failed: {exc}")
        print("Run: pip install soccerdata")
        return False


# ---------------------------------------------------------------------------
# Test 2 — Check available data sources
# ---------------------------------------------------------------------------

def test_available_sources() -> None:
    """
    List all data sources available in soccerdata
    and which competitions each one covers.
    """
    print("\n" + "=" * 55)
    print("TEST 2 — AVAILABLE DATA SOURCES")
    print("=" * 55)

    import soccerdata as sd

    # List all reader classes available
    readers = [
        attr for attr in dir(sd)
        if not attr.startswith("_")
    ]
    print("Available reader classes:")
    for reader in readers:
        print(f"  {reader}")


# ---------------------------------------------------------------------------
# Test 3 — FBref reader for World Cup
# ---------------------------------------------------------------------------

def test_fbref_wc() -> None:
    """
    Test FBref reader specifically for World Cup 2026 data.
    FBref lost Opta license in Jan 2026 so we check what remains.
    """
    print("\n" + "=" * 55)
    print("TEST 3 — FBREF WORLD CUP 2026")
    print("=" * 55)

    import soccerdata as sd

    try:
        # Initialise FBref reader for World Cup
        # WC is the competition code for FIFA World Cup
        print("Initialising FBref reader for WC 2026...")
        fbref = sd.FBref(leagues="WC", seasons=2026)

        # Test 1 — try to get schedule
        print("\nFetching match schedule...")
        schedule = fbref.read_schedule()
        print(f"Schedule rows returned: {len(schedule)}")
        if len(schedule) > 0:
            print(f"Columns: {list(schedule.columns)}")
            print(f"\nSample:\n{schedule.head(3)}")

    except Exception as exc:
        print(f"FBref WC test failed: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Test 4 — FBref match stats
# ---------------------------------------------------------------------------

def test_fbref_match_stats() -> None:
    """
    Test if FBref returns team match statistics including
    possession, shots, and xG for WC 2026 matches.
    These are our core analysis metrics.
    """
    print("\n" + "=" * 55)
    print("TEST 4 — FBREF MATCH STATISTICS")
    print("=" * 55)

    import soccerdata as sd

    try:
        fbref = sd.FBref(leagues="WC", seasons=2026)

        print("Fetching team match stats...")
        stats = fbref.read_team_match_stats()

        print(f"Rows returned: {len(stats)}")

        if len(stats) > 0:
            print(f"Columns available: {list(stats.columns)}")

            # Check specifically for our key metrics
            key_metrics = [
                "possession", "shots", "shots_on_target",
                "xg", "xga", "passes", "passes_pct"
            ]
            found = [
                m for m in key_metrics
                if any(m in col.lower() for col in stats.columns)
            ]
            missing = [m for m in key_metrics if m not in found]

            print(f"\nKey metrics found    : {found}")
            print(f"Key metrics missing  : {missing}")
            print(f"\nSample data:\n{stats.head(3)}")

    except Exception as exc:
        print(f"Match stats test failed: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Test 5 — FBref match events
# ---------------------------------------------------------------------------

def test_fbref_events() -> None:
    """
    Test if FBref returns match events with minute timestamps.
    Goals, substitutions, and cards with exact minutes are
    the most critical data for our HB window analysis.
    """
    print("\n" + "=" * 55)
    print("TEST 5 — FBREF MATCH EVENTS")
    print("=" * 55)

    import soccerdata as sd

    try:
        fbref = sd.FBref(leagues="WC", seasons=2026)

        print("Fetching match events...")
        events = fbref.read_events()

        print(f"Events returned: {len(events)}")

        if len(events) > 0:
            print(f"Columns: {list(events.columns)}")

            # Check for minute column — critical for HB analysis
            minute_cols = [
                c for c in events.columns
                if "minute" in c.lower() or "min" in c.lower()
            ]
            print(f"Minute columns found: {minute_cols}")
            print(f"\nSample events:\n{events.head(10)}")

    except Exception as exc:
        print(f"Events test failed: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Test 6 — Check what other leagues work (baseline validation)
# ---------------------------------------------------------------------------

def test_baseline_league() -> None:
    """
    Test FBref with a known working league to confirm the library
    itself is functioning, separate from WC-specific issues.
    If this works but WC does not, the issue is WC coverage.
    If this also fails, the issue is the library or FBref access.
    """
    print("\n" + "=" * 55)
    print("TEST 6 — BASELINE VALIDATION (Premier League 2024)")
    print("=" * 55)

    import soccerdata as sd

    try:
        # Try Premier League 2024 as a known working baseline
        fbref = sd.FBref(
            leagues="ENG-Premier League",
            seasons=2024
        )

        print("Fetching Premier League schedule (first 3 matches)...")
        schedule = fbref.read_schedule()

        if len(schedule) > 0:
            print(f"Schedule returned {len(schedule)} matches")
            print("FBref reader is working — coverage issue is WC-specific")
        else:
            print("Empty schedule — FBref access may be fully blocked")

    except Exception as exc:
        print(
            f"Baseline test failed: {type(exc).__name__}: {exc}"
        )
        print(
            "This suggests the FBref reader itself has an issue"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run all soccerdata tests in sequence.
    Results tell us whether this library can serve as our
    primary data source for WC 2026 advanced metrics.
    """
    print("=" * 55)
    print("SOCCERDATA LIBRARY TEST — WC 2026")
    print("=" * 55)

    # Must pass before other tests
    if not test_import():
        print("Cannot continue — fix import first.")
        sys.exit(1)

    test_available_sources()
    test_fbref_wc()
    test_fbref_match_stats()
    test_fbref_events()
    test_baseline_league()

    print("\n" + "=" * 55)
    print("ALL TESTS COMPLETE")
    print("=" * 55)


if __name__ == "__main__":
    main()