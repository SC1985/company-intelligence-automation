#!/usr/bin/env python3
import asyncio
import importlib
import inspect
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from mailer import send_html_email

HERE = Path(__file__).resolve().parent
# Ensure we can import `main.py` from src/
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

CANDIDATE_FUNCS = [
    "build_report_html",
    "generate_report_html",
    "render_report_html",
    "build_weekly_html",
    "generate_email_html",
    "build_html",
]

CANDIDATE_CLASSES = [
    "StrategicIntelligenceEngine",
    "IntelligenceEngine",
    "ReportEngine",
]

CANDIDATE_METHODS = [
    # one-shot builders preferred
    "build_report_html",
    "generate_report_html",
    "render_html",
    "to_html",
    "compose_html",
    "make_html",
    # staged pipeline (call if present in sequence)
    "_harvest_constellation_data",
    "_synthesize_strategic_news",
    "_architect_executive_brief",
]

async def maybe_call(fn, *args, **kwargs):
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result

async def build_dynamic_html(logger):
    # Try: import main module
    try:
        app = importlib.import_module("main")
    except Exception as e:
        logger.error("Could not import src/main.py as module 'main': %s", e)
        app = None

    # Strategy 1: direct top-level function
    if app:
        for name in CANDIDATE_FUNCS:
            fn = getattr(app, name, None)
            if callable(fn):
                logger.info("Using main.%s()", name)
                html = await maybe_call(fn)
                if isinstance(html, dict) and "html" in html:
                    html = html["html"]
                if isinstance(html, str) and html.strip():
                    return html

    # Strategy 2: class-based engine
    if app:
        for cls_name in CANDIDATE_CLASSES:
            cls = getattr(app, cls_name, None)
            if cls:
                logger.info("Using engine class: %s", cls_name)
                engine = cls()  # assume no-arg init
                # Preferred single-call methods
                for m in CANDIDATE_METHODS[:6]:
                    fn = getattr(engine, m, None)
                    if callable(fn):
                        logger.info("Using engine.%s()", m)
                        html = await maybe_call(fn)
                        if isinstance(html, dict) and "html" in html:
                            html = html["html"]
                        if isinstance(html, str) and html.strip():
                            return html
                # Staged pipeline if available
                harvest = getattr(engine, "_harvest_constellation_data", None)
                synth = getattr(engine, "_synthesize_strategic_news", None)
                arch = getattr(engine, "_architect_executive_brief", None)
                if callable(harvest) and callable(synth) and callable(arch):
                    logger.info("Using staged pipeline: harvest -> synthesize -> architect")
                    market = await maybe_call(harvest)
                    news = await maybe_call(synth)
                    html = await maybe_call(arch, market, news)
                    if isinstance(html, str) and html.strip():
                        return html

    # Strategy 3: run main as a script and read a file emitted by it
    out_path = Path("out/email_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["EMIT_HTML_PATH"] = str(out_path)
    try:
        logger.info("Attempting subprocess fallback: python src/main.py (expecting EMIT_HTML_PATH)")
        cp = subprocess.run([sys.executable, "src/main.py"], env=env, text=True, capture_output=True, timeout=1200)
        if out_path.exists():
            html = out_path.read_text(encoding="utf-8", errors="ignore")
            if html.strip():
                return html
        # If not emitted, try stdout (last resort)
        if cp.stdout and "<html" in cp.stdout.lower():
            return cp.stdout
        logger.error("Subprocess fallback failed. Return code: %s\nstdout: %s\nstderr: %s", cp.returncode, cp.stdout[-1000:], cp.stderr[-1000:])
    except Exception as e:
        logger.error("Subprocess fallback error: %s", e)

    raise RuntimeError("Could not dynamically build HTML with any strategy. Expose a function or class method that returns HTML.")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ci-entrypoint")

    html = await build_dynamic_html(logger)

    today = datetime.now().strftime("%B %d, %Y")
    subject = f"\ud83d\udcca Weekly Company Intelligence Report — {today}"

    send_html_email(html=html, subject=subject, logger=logger)
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
