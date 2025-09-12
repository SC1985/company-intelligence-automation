#!/usr/bin/env python3
# Investment Edge - Enhanced Entry Point with Dynamic Subject Lines
import asyncio
import importlib
import inspect
import logging
import os
import sys
import re
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

def extract_hero_headline(html):
    """Extract hero headline from HTML comment."""
    if not html:
        return None
    
    # Look for the special comment
    match = re.search(r'<!-- HERO_HEADLINE:(.*?) -->', html)
    if match:
        headline = match.group(1).strip()
        # Unescape HTML entities
        headline = headline.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        return headline if headline else None
    return None

def generate_hero_based_subject(hero_headline=None):
    """Generate Investment Edge subject line based on hero headline or fallback."""
    today = datetime.now().strftime("%B %d")
    current_hour = datetime.now().hour
    
    # Time-aware emoji
    if 5 <= current_hour < 12:
        time_emoji = "🌅"
    elif 12 <= current_hour < 17:
        time_emoji = "📊"
    elif 17 <= current_hour < 21:
        time_emoji = "🌆"
    else:
        time_emoji = "🌙"
    
    if hero_headline:
        # Clean up the headline for subject use
        hero_headline = hero_headline.strip()
        
        # If headline is too long, truncate intelligently
        if len(hero_headline) > 60:
            # Try to cut at a word boundary
            hero_headline = hero_headline[:57].rsplit(' ', 1)[0] + "..."
        
        # Hero-based subject lines (using Investment Edge branding)
        subjects = [
            f"{time_emoji} {hero_headline}",
            f"{hero_headline} • {today}",
            f"📰 {hero_headline}",
            f"⚡ {hero_headline}",
        ]
        
        # Pick one based on time of day
        index = current_hour % len(subjects)
        return subjects[index]
    
    else:
        # Fallback subjects with Investment Edge branding
        subjects = [
            f"{time_emoji} Investment Edge • {today}",
            f"📊 Portfolio Edge • {today}",
            f"⚡ Today's Market Edge",
            f"🎯 Investment Updates • {today}",
            f"💡 Strategic Edge • {today}",
        ]
        
        # Rotate based on day
        day_index = datetime.now().timetuple().tm_yday % len(subjects)
        return subjects[day_index]

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ci-entrypoint")

    html = None
    if os.getenv("NEXTGEN_DIGEST", "false").lower() == "true":
        try:
            logger.info("Using NextGen Investment Edge renderer")
            ng = importlib.import_module("nextgen_digest")
            html = await ng.build_nextgen_html(logger)
            logger.info("NextGen Investment Edge HTML generated successfully")
        except Exception as e:
            logger.error("NextGen Investment Edge failed: %s", e)

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

    # Extract hero headline from HTML for subject generation
    hero_headline = extract_hero_headline(html)
    
    if hero_headline:
        logger.info(f"Extracted hero headline: {hero_headline[:50]}...")
    
    # Generate subject based on hero headline with Investment Edge branding
    subject = generate_hero_based_subject(hero_headline)
    
    logger.info(f"Generated subject: {subject}")
    logger.info(f"Email HTML length: {len(html)} characters")

    send_html_email(html=html, subject=subject, logger=logger)
    logger.info("Investment Edge email dispatch completed successfully")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
