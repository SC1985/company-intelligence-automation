# History Provider Patch (v1)

This patch fills **1W / 1M / YTD**, **52‑week Low/High**, and **sparklines** for every ticker
by adding a robust history provider (Yahoo Finance via `yfinance`, with Stooq CSV fallback).
It mirrors the approach in your KOPN updater (week=5d, month=21d, year≈252d, 52w bounds).

## Install
Unzip at the repo root to overwrite:
- `.github/workflows/weekly-report.yml`
- `src/history_provider.py`
- `src/nextgen_digest.py`

## Requirements
The workflow installs: `yfinance pandas requests matplotlib pillow`

## Logs
For each ticker you’ll see: `XYZ: history provider=yf|stooq bars=###`

