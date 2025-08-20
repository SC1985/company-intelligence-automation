placeholder
# Next‑Gen Digest Patch (FULL)

Investor-first layout:
- Heat strip (1D) + top movers
- Company cards with 1D/1W/1M/YTD chips (red/green), sparkline (inline PNG), 52-week range, 1 headline

## Install
Unzip at the repo root to create/overwrite:
- `.github/workflows/weekly-report.yml`
- `src/ci_entrypoint.py`
- `src/nextgen_digest.py`
- `src/render_email.py`
- `src/chartgen.py`

## Run
Actions → “Executive Intelligence Brief (NextGen Dynamic)” → Run workflow.
The workflow sets `NEXTGEN_DIGEST=true`. If anything fails, it falls back automatically.
