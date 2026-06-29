# FIFA World Cup 2026 — Hydration Break Impact Analysis

## Research Goal
Analysing the impact of mandatory hydration breaks (HBs)
on match dynamics in the FIFA World Cup 2026, with a focus
on tactical resets, tempo disruption, and scoring pattern shifts.

## Hypotheses
- H1: Trailing teams show measurable improvement after HBs
- H2: Dominant team tempo decreases post-HB regardless of score
- H3: Goal probability changes significantly in post-HB windows
- H4: HB effects are more pronounced in high heat/humidity conditions
- H5: Teams making tactical changes at HB show greater improvement

## Tech Stack
- Python 3.13
- SQLite (data storage)
- pandas, numpy, scipy (analysis)
- scikit-learn, XGBoost (modelling)
- matplotlib, seaborn, plotly (visualisation)
- mplsoccer (football pitch maps)
- Streamlit (dashboard)

## Data Sources
- football-data.org (match results and standings)
- FBref.com (match statistics and events)
- Open-Meteo API (weather data)
- Manual hydration break log

## Project Structure
wc2026_hb_analysis/

├── data/

│   ├── raw/          # SQLite database

│   ├── processed/    # Analysis-ready CSV files

│   └── exports/      # Final output files

├── scripts/          # Data collection pipeline

├── notebooks/        # EDA and analysis notebooks

└── logs/             # Pipeline execution logs

## Status
🟡 In progress — Data collection phase