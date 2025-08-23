#!/usr/bin/env python3
import asyncio
import importlib
import inspect
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from mailer import send_html_email

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

async def maybe_call(fn, *args, **kwargs):
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **kwargs)
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ci-entrypoint")

    html = None
    if os.getenv("NEXTGEN_DIGEST", "false").lower() == "true":
        try:
            logger.info("Using NextGen digest renderer")
            ng = importlib.import_module("nextgen_digest")
            html = await ng.build_nextgen_html(logger)
            logger.info("NextGen digest HTML generated successfully")
        except Exception as e:
            logger.error("NextGen digest failed: %s", e)

    if not html:
        logger.info("Falling back to engine dynamic builder")
        CANDIDATE_FUNCS = [
            "build_report_html","generate_report_html","render_report_html",
            "build_weekly_html","generate_email_html","build_html",
        ]
        CANDIDATE_CLASSES = ["StrategicIntelligenceEngine","IntelligenceEngine","ReportEngine"]
        CANDIDATE_METHODS = [
            "build_report_html","generate_report_html","render_html","to_html","compose_html","make_html",
            "_harvest_constellation_data","_synthesize_strategic_news","_architect_executive_brief",
        ]
        try:
            app = importlib.import_module("main")
        except Exception as e:
            logger.error("Could not import src/main.py as module 'main': %s", e)
            app = None

        if app:
            for name in CANDIDATE_FUNCS:
                fn = getattr(app, name, None)
                if callable(fn):
                    logger.info("Using main.%s()", name)
                    html = await maybe_call(fn)
                    if isinstance(html, dict) and "html" in html:
                        html = html["html"]
                    if isinstance(html, str) and html.strip():
                        break

        if not html and app:
            for cls_name in CANDIDATE_CLASSES:
                cls = getattr(app, cls_name, None)
                if cls:
                    logger.info("Using engine class: %s", cls_name)
                    engine = cls()
                    for m in CANDIDATE_METHODS[:6]:
                        fn = getattr(engine, m, None)
                        if callable(fn):
                            logger.info("Using engine.%s()", m)
                            html = await maybe_call(fn)
                            if isinstance(html, dict) and "html" in html:
                                html = html["html"]
                            if isinstance(html, str) and html.strip():
                                break
                    if not html:
                        harvest = getattr(engine, "_harvest_constellation_data", None)
                        synth = getattr(engine, "_synthesize_strategic_news", None)
                        arch = getattr(engine, "_architect_executive_brief", None)
                        if callable(harvest) and callable(synth) and callable(arch):
                            logger.info("Using staged pipeline: harvest -> synthesize -> architect")
                            market = await maybe_call(harvest)
                            news = await maybe_call(synth)
                            html = await maybe_call(arch, market, news)

    if not html or not isinstance(html, str):
        raise RuntimeError("Could not build HTML (NextGen + fallbacks exhausted).")

    # 🔥 NEW: Enhanced subject line generation
    today = datetime.now().strftime("%B %d, %Y")
    current_hour = datetime.now().hour
    
    # Time-aware subject lines
    if 5 <= current_hour < 12:
        time_emoji = "🌅"
        time_context = "Morning"
    elif 12 <= current_hour < 17:
        time_emoji = "☀️" 
        time_context = "Midday"
    elif 17 <= current_hour < 21:
        time_emoji = "🌆"
        time_context = "Evening"  
    else:
        time_emoji = "🌙"
        time_context = "Late"
    
    # Check for market signals in HTML to customize subject
    alert_count = html.count('MAJOR') + html.count('SIGNIFICANT') if html else 0
    if alert_count > 2:
        urgency_emoji = "🔥"
        urgency_text = f" • {alert_count} Key Signals"
    elif alert_count > 0:
        urgency_emoji = "⚡"
        urgency_text = f" • {alert_count} Updates"
    else:
        urgency_emoji = time_emoji
        urgency_text = ""
        
    subject = f"{urgency_emoji} Intelligence Digest • {today.split(',')[0]}{urgency_text}"
    
    logger.info(f"Generated subject: {subject}")
    logger.info(f"Email HTML length: {len(html)} characters")

    send_html_email(html=html, subject=subject, logger=logger)
    logger.info("Email dispatch completed successfully")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
