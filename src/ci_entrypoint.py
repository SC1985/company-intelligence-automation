#!/usr/bin/env python3
import asyncio
import logging
import os
from datetime import datetime

# Import your existing engine from src/main.py without executing it
from main import StrategicIntelligenceEngine
from mailer import send_html_email

def read_template_html():
    # Prefer templates/email_report.html; fall back to sample_email_report.html and then engine-generated HTML
    candidates = [
        os.getenv("HTML_TEMPLATE_PATH"),
        os.path.join("templates", "email_report.html"),
        "sample_email_report.html",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), os.path.basename(path)
    return None, None

async def build_dynamic_html(logger):
    engine = StrategicIntelligenceEngine()
    logger.info("Collecting market intelligence…")
    market = await engine._harvest_constellation_data()
    logger.info("Synthesizing news intelligence…")
    news = await engine._synthesize_strategic_news()
    logger.info("Composing executive brief…")
    html = engine._architect_executive_brief(market, news)
    return html

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("ci-entrypoint")

    use_template_first = os.getenv("USE_TEMPLATE_FIRST", "true").lower() == "true"

    html = None
    chosen = None
    if use_template_first:
        html, chosen = read_template_html()
        if html:
            logger.info(f"Using HTML template: {chosen}")
        else:
            logger.info("No HTML template found; generating dynamic report.")

    if not html:
        html = await build_dynamic_html(logger)

    # Subject: prefer template's header wording
    today = datetime.now().strftime("%B %d, %Y")
    subject = f"📊 Weekly Company Intelligence Report — {today}"

    send_html_email(html=html, subject=subject, logger=logger)
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))
