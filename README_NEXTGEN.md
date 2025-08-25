# Next‑Gen Daily Digest

Daily investor intelligence with enhanced mobile experience:
- Breaking news prioritization with fallback to market analysis
- Top mover highlighting with live price changes
- Company cards with 1D/1W/1M/YTD chips (red/green), 52-week range
- Mobile-optimized with wider cards and premium typography
- Smart subject lines using hero headlines

## Install
Place these files at the repo root:
- `.github/workflows/daily-digest.yml` (renamed from weekly-report.yml)
- `src/ci_entrypoint.py`
- `src/nextgen_digest.py`
- `src/render_email.py`
- `src/chartgen.py`

## Schedule
Runs daily at 8am Central Time (CDT/CST adjusted)

## Manual Run
Actions → "Daily Intelligence Digest" → Run workflow

The workflow sets `NEXTGEN_DIGEST=true`. If anything fails, it falls back automatically.
