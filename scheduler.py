#!/usr/bin/env python3
"""
Scheduler for MaisVantagens scraper.
Runs scraper.run() at: 01:00, 06:00, 10:00, 13:00, 17:00, 20:00 (container timezone = America/Sao_Paulo)
"""

import asyncio
import logging
import time

import schedule

from scraper import run

log = logging.getLogger('scheduler')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)


def job():
    log.info('Scheduler triggered — starting scraper run')
    try:
        asyncio.run(run())
    except Exception as e:
        log.error('Scraper run failed with exception: %s', e, exc_info=True)


schedule.every().day.at('01:00').do(job)
schedule.every().day.at('06:00').do(job)
schedule.every().day.at('10:00').do(job)
schedule.every().day.at('13:00').do(job)
schedule.every().day.at('17:00').do(job)
schedule.every().day.at('20:00').do(job)

log.info('Scheduler started. Waiting for next scheduled time...')
while True:
    schedule.run_pending()
    time.sleep(30)
