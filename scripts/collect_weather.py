# scripts/collect_weather.py
"""
Module: collect_weather.py
Purpose: Collect historical weather data for every WC 2026 match
         using the Open-Meteo free historical archive API.
         No API key required — completely free.

         Uses venue coordinates from kaggle_venues and kickoff
         times from kaggle_matches to fetch conditions at the
         exact hour of each match.

         Weather serves two roles in our analysis:
         - Control variable: heat and humidity are the stated
           justification for mandatory HBs. We need to measure
           whether conditions actually warranted the break.
         - H4 variable: does the tactical impact of HBs differ
           between high heat and cool/indoor matches?

         Output: kaggle_weather table in SQLite +
                 data/processed/weather_data.csv

Author: Kunal R
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = "data/raw/wc2026_raw.db"
LOG_PATH = "logs/collect_weather.log"
OUTPUT_CSV = "data/processed/weather_data.csv"
REQUEST_DELAY = 1.0
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# IANA timezone lookup by country and city
# Required by Open-Meteo — it returns local time in the response
TIMEZONE_MAP = {
    # USA — spans three time zones
    "East Rutherford": "America/New_York",
    "Foxborough":      "America/New_York",
    "Philadelphia":    "America/New_York",
    "Atlanta":         "America/New_York",
    "Miami Gardens":   "America/New_York",
    "Houston":         "America/Chicago",
    "Kansas City":     "America/Chicago",
    "Arlington":       "America/Chicago",
    "Inglewood":       "America/Los_Angeles",
    "Santa Clara":     "America/Los_Angeles",
    "Seattle":         "America/Los_Angeles",
    # Mexico
    "Mexico City":     "America/Mexico_City",
    "Zapopan":         "America/Mexico_City",
    "Guadalupe":       "America/Mexico_City",
    # Canada
    "Toronto":         "America/Toronto",
    "Vancouver":       "America/Vancouver"
}

DEFAULT_TIMEZONE = "America/Chicago"


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
# Helper functions
# ---------------------------------------------------------------------------

def get_timezone(city: str) -> str:
    """
    Resolve IANA timezone string for a venue city.

    Args:
        city: City name from kaggle_venues table.

    Returns:
        IANA timezone string e.g. 'America/New_York'.
    """
    return TIMEZONE_MAP.get(city, DEFAULT_TIMEZONE)


def parse_kickoff_hour(kickoff_utc: str) -> int:
    """
    Extract the UTC hour from a kickoff time string.
    Kaggle stores kickoff_time_utc as 'HH:MM'.

    Args:
        kickoff_utc: Time string in 'HH:MM' format.

    Returns:
        Integer hour (0-23). Defaults to 15 if unparseable.
    """
    try:
        return int(str(kickoff_utc).split(":")[0])
    except (ValueError, AttributeError, IndexError):
        logger.warning(
            "Could not parse kickoff time '%s', defaulting to 15:00",
            kickoff_utc
        )
        return 15


def fetch_hourly_weather(lat: float,
                          lon: float,
                          date: str,
                          tz: str) -> dict | None:
    """
    Fetch full day hourly weather from Open-Meteo archive API
    for a specific date and location.

    Open-Meteo uses ERA5 reanalysis data — the same dataset
    used in peer-reviewed climate and sports science research.
    This makes it an academically credible source for our paper.

    Variables fetched:
    - temperature_2m         Air temp at 2m height in Celsius
    - relative_humidity_2m   Humidity as percentage
    - apparent_temperature   Feels-like temp (wind chill / heat index)
    - precipitation          Rainfall in mm
    - wind_speed_10m         Wind speed at 10m in km/h
    - cloud_cover            Cloud cover as percentage

    Args:
        lat: Venue latitude.
        lon: Venue longitude.
        date: Match date string in 'YYYY-MM-DD' format.
        tz: IANA timezone string for the venue.

    Returns:
        Raw API response dictionary or None on failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "wind_speed_10m",
            "cloud_cover"
        ]),
        "timezone": tz,
        "wind_speed_unit": "kmh"
    }

    try:
        response = requests.get(
            BASE_URL, params=params, timeout=15
        )
        response.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return response.json()

    except requests.exceptions.RequestException as exc:
        logger.error("Open-Meteo request failed: %s", exc)
        return None


def extract_hour_conditions(raw: dict,
                             hour: int) -> dict:
    """
    Pull weather conditions for a specific hour from the full
    day of hourly data returned by Open-Meteo.

    Open-Meteo returns 24 values per variable (one per hour).
    We use the kickoff hour to index into the correct position.

    Args:
        raw: Raw Open-Meteo API response.
        hour: UTC hour of kickoff (0-23).

    Returns:
        Dictionary of weather values at the kickoff hour.
    """
    hourly = raw.get("hourly", {})
    times = hourly.get("time", [])

    # Find the array index for our kickoff hour
    # Times are formatted as '2026-06-11T15:00'
    hour_index = None
    for i, t in enumerate(times):
        if f"T{hour:02d}:" in t:
            hour_index = i
            break

    # Fallback to direct hour indexing if string search fails
    if hour_index is None:
        hour_index = min(hour, len(times) - 1)

    def safe_get(key: str) -> float | None:
        values = hourly.get(key, [])
        if hour_index < len(values):
            return values[hour_index]
        return None

    return {
        "temp_celsius":       safe_get("temperature_2m"),
        "humidity_pct":       safe_get("relative_humidity_2m"),
        "feels_like_celsius": safe_get("apparent_temperature"),
        "precipitation_mm":   safe_get("precipitation"),
        "wind_speed_kmh":     safe_get("wind_speed_10m"),
        "cloud_cover_pct":    safe_get("cloud_cover")
    }


def calculate_heat_index(temp_c: float | None,
                          humidity: float | None) -> float | None:
    """
    Calculate Heat Index using the Steadman-Rothfusz formula.

    The Heat Index represents the perceived temperature accounting
    for humidity. It is the metric sports medicine professionals
    use to assess exertional heat risk in athletes.

    FIFA's historical threshold for triggering conditional HBs
    in 2014 and 2022 was a Wet Bulb Globe Temperature (WBGT)
    of 32 degrees Celsius. The Heat Index is a close proxy for
    WBGT and the appropriate measure given available data.

    Formula source: Rothfusz (1990), NOAA Technical Attachment SR/SSD
    This is the same formula used by US National Weather Service.

    Args:
        temp_c: Air temperature in Celsius.
        humidity: Relative humidity as percentage (0-100).

    Returns:
        Heat index in Celsius rounded to 2 decimal places,
        or None if inputs are missing.
    """
    if temp_c is None or humidity is None:
        return None

    # Steadman formula operates in Fahrenheit
    t = (temp_c * 9 / 5) + 32
    r = humidity

    # Below 80F (26.7C) heat index is same as temperature
    if t < 80:
        return round(temp_c, 2)

    hi_f = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * r
        - 0.22475541 * t * r
        - 0.00683783 * t ** 2
        - 0.05481717 * r ** 2
        + 0.00122874 * t ** 2 * r
        + 0.00085282 * t * r ** 2
        - 0.00000199 * t ** 2 * r ** 2
    )

    return round((hi_f - 32) * 5 / 9, 2)


def classify_heat_stress(heat_index_c: float | None) -> str:
    """
    Classify match conditions into heat stress categories.
    Used as a categorical feature in our H4 analysis and
    as a grouping variable for all comparative analyses.

    Categories based on NOAA and Korey Stringer Institute
    guidelines for exertional heat stress in athletes:
    - Low:      Below 27C  — minimal heat risk
    - Moderate: 27-31C     — elevated caution advised
    - High:     32-37C     — above FIFA's historical HB threshold
    - Extreme:  38C+       — dangerous conditions

    Args:
        heat_index_c: Heat index in Celsius.

    Returns:
        Heat stress category as string.
    """
    if heat_index_c is None:
        return "Unknown"
    if heat_index_c < 27:
        return "Low"
    elif heat_index_c < 32:
        return "Moderate"
    elif heat_index_c < 38:
        return "High"
    else:
        return "Extreme"


# ---------------------------------------------------------------------------
# Core collection function
# ---------------------------------------------------------------------------

def collect_weather(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Collect weather conditions at kickoff for all 104 WC 2026 matches.

    Strategy:
    1. Join kaggle_matches with kaggle_venues to get coordinates
    2. For each match fetch hourly weather from Open-Meteo
    3. Extract conditions at the kickoff hour specifically
    4. Calculate derived metrics (heat index, stress category)
    5. Cache by venue+date to avoid duplicate API calls

    The cache is important — multiple matches at the same stadium
    on the same day share one API call. This keeps us well within
    Open-Meteo's fair use limits.

    Args:
        conn: Active SQLite connection to project database.

    Returns:
        DataFrame with one weather row per match (104 rows total).
    """
    logger.info("Loading match and venue data...")

    matches_df = pd.read_sql_query("""
        SELECT
            m.match_id,
            m.date,
            m.kickoff_time_utc,
            v.venue_id,
            v.stadium_name,
            v.city,
            v.country,
            v.latitude,
            v.longitude,
            v.elevation_meters
        FROM kaggle_matches m
        JOIN kaggle_venues v ON m.venue_id = v.venue_id
        ORDER BY m.date, m.match_id
    """, conn)

    logger.info(
        "Found %d matches across %d unique venues.",
        len(matches_df),
        matches_df["venue_id"].nunique()
    )

    # Cache: venue_id + date -> raw API response
    api_cache = {}
    records = []
    api_calls_made = 0
    api_calls_saved = 0

    for idx, match in matches_df.iterrows():
        match_id = int(match["match_id"])
        date_str = str(match["date"])[:10]
        city = match["city"]
        tz = get_timezone(city)
        kickoff_hour = parse_kickoff_hour(match["kickoff_time_utc"])
        cache_key = f"{int(match['venue_id'])}_{date_str}"

        # Fetch or retrieve from cache
        if cache_key not in api_cache:
            logger.info(
                "API call %d: %s on %s",
                api_calls_made + 1,
                match["stadium_name"],
                date_str
            )
            raw = fetch_hourly_weather(
                lat=match["latitude"],
                lon=match["longitude"],
                date=date_str,
                tz=tz
            )
            api_cache[cache_key] = raw
            api_calls_made += 1
        else:
            api_calls_saved += 1
            raw = api_cache[cache_key]

        # Extract conditions at kickoff
        if raw:
            conditions = extract_hour_conditions(raw, kickoff_hour)
        else:
            logger.warning(
                "No weather data for match %d — nulls inserted.",
                match_id
            )
            conditions = {
                "temp_celsius": None,
                "humidity_pct": None,
                "feels_like_celsius": None,
                "precipitation_mm": None,
                "wind_speed_kmh": None,
                "cloud_cover_pct": None
            }

        # Derived metrics
        hi = calculate_heat_index(
            conditions["temp_celsius"],
            conditions["humidity_pct"]
        )
        stress = classify_heat_stress(hi)

        records.append({
            "match_id":                match_id,
            "date":                    date_str,
            "kickoff_hour_utc":        kickoff_hour,
            "stadium_name":            match["stadium_name"],
            "city":                    city,
            "country":                 match["country"],
            "elevation_meters":        match["elevation_meters"],
            "timezone":                tz,
            "temp_celsius":            conditions["temp_celsius"],
            "humidity_pct":            conditions["humidity_pct"],
            "feels_like_celsius":      conditions["feels_like_celsius"],
            "precipitation_mm":        conditions["precipitation_mm"],
            "wind_speed_kmh":          conditions["wind_speed_kmh"],
            "cloud_cover_pct":         conditions["cloud_cover_pct"],
            "heat_index_celsius":      hi,
            "heat_stress_category":    stress,
            "above_fifa_threshold_32c": 1 if hi and hi >= 32 else 0,
            "collected_at":            datetime.now(
                timezone.utc
            ).isoformat()
        })

    logger.info(
        "Collection complete. API calls made: %d | Saved by cache: %d",
        api_calls_made,
        api_calls_saved
    )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Save and report
# ---------------------------------------------------------------------------

def save_results(conn: sqlite3.Connection,
                 df: pd.DataFrame) -> None:
    """
    Save weather DataFrame to SQLite and CSV.

    Args:
        conn: Active SQLite connection.
        df: Weather DataFrame with one row per match.
    """
    os.makedirs("data/processed", exist_ok=True)

    df.to_sql(
        "kaggle_weather",
        conn,
        if_exists="replace",
        index=False
    )
    logger.info(
        "Saved %d rows to kaggle_weather table.", len(df)
    )

    df.to_csv(OUTPUT_CSV, index=False)
    logger.info("Saved to %s", OUTPUT_CSV)


def print_summary(df: pd.DataFrame) -> None:
    """
    Print a human readable summary of collected weather data.

    Args:
        df: Completed weather DataFrame.
    """
    print("\n" + "=" * 55)
    print("WEATHER COLLECTION SUMMARY")
    print("=" * 55)

    total = len(df)
    complete = df["temp_celsius"].notnull().sum()
    missing = total - complete

    print(f"\nMatches total         : {total}")
    print(f"Weather collected     : {complete}")
    print(f"Missing data          : {missing}")

    if complete > 0:
        print(f"\nTemperature (Celsius):")
        print(f"  Minimum           : "
              f"{df['temp_celsius'].min():.1f}")
        print(f"  Maximum           : "
              f"{df['temp_celsius'].max():.1f}")
        print(f"  Average           : "
              f"{df['temp_celsius'].mean():.1f}")

        print(f"\nHumidity (%):")
        print(f"  Minimum           : "
              f"{df['humidity_pct'].min():.0f}")
        print(f"  Maximum           : "
              f"{df['humidity_pct'].max():.0f}")
        print(f"  Average           : "
              f"{df['humidity_pct'].mean():.0f}")

        print(f"\nHeat Index (Celsius):")
        hi_valid = df["heat_index_celsius"].dropna()
        if len(hi_valid) > 0:
            print(f"  Minimum           : {hi_valid.min():.1f}")
            print(f"  Maximum           : {hi_valid.max():.1f}")
            print(f"  Average           : {hi_valid.mean():.1f}")

        above = df["above_fifa_threshold_32c"].sum()
        print(f"\nMatches above 32C HI  : {above} of {total}")

        print(f"\nHeat stress breakdown:")
        for cat, cnt in (
            df["heat_stress_category"]
            .value_counts()
            .items()
        ):
            bar = "█" * int(cnt / total * 30)
            print(f"  {cat:<12} {cnt:>3}  {bar}")

        print(f"\nConditions by country:")
        for country, group in df.groupby("country"):
            avg_t = group["temp_celsius"].mean()
            avg_h = group["humidity_pct"].mean()
            print(f"  {country:<5} "
                  f"avg temp: {avg_t:.1f}C  "
                  f"avg humidity: {avg_h:.0f}%  "
                  f"({len(group)} matches)")

    print("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Run the complete weather collection pipeline.
    Fetches conditions at kickoff for all 104 WC 2026 matches.
    Saves to SQLite database and CSV for use in analysis notebooks.
    """
    logger.info("=" * 55)
    logger.info("WC 2026 WEATHER COLLECTION STARTED")
    logger.info("=" * 55)

    conn = sqlite3.connect(DB_PATH)

    weather_df = collect_weather(conn)
    save_results(conn, weather_df)
    print_summary(weather_df)

    conn.close()

    logger.info("=" * 55)
    logger.info("WEATHER COLLECTION COMPLETE")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()