#!/usr/bin/env python3
"""
Automated scraper for Mais Vantagens attendance reports.
Logs in via Playwright (handles reCAPTCHA v3), scrapes data, and uploads to Supabase.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ============================================
# Configuration
# ============================================
SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / '.env')

INFORNET_LOGIN = os.getenv('INFORNET_LOGIN')
INFORNET_PASSWORD = os.getenv('INFORNET_PASSWORD')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
TABLE_NAME = os.getenv('TABLE_NAME', 'historico_atise')

BASE_URL = 'https://sistemas.infornet.com.br'
LOGIN_URL = f'{BASE_URL}/webassist/maisvantagens/index.php'
REPORT_URL = f'{BASE_URL}/webassist/maisvantagens/cliente/rel_atendimentos.php'

COOKIES_FILE = SCRIPT_DIR / 'cookies.json'

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
ALERT_EMAILS = [e.strip() for e in os.getenv('ALERT_EMAILS', '').split(',') if e.strip()]
STALE_DATA_DAYS = int(os.getenv('STALE_DATA_DAYS', '4'))

# ============================================
# Log Directory (daily log + 7-day history)
# ============================================
LOGS_DIR = SCRIPT_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
DAILY_LOG_FILE = LOGS_DIR / f'scraper_{datetime.now().strftime("%Y-%m-%d")}.log'

# ============================================
# Logging
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(DAILY_LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('scraper')


# ============================================
# Cookie Management
# ============================================
def save_cookies(cookies: list):
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies, f, indent=2)
    log.info('Cookies saved to %s', COOKIES_FILE)


def load_cookies() -> list:
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        if cookies:
            log.info('Loaded %d cookies from file', len(cookies))
            return cookies
    return []


def cookies_to_session(cookies: list) -> requests.Session:
    session = requests.Session()
    for c in cookies:
        session.cookies.set(
            c['name'],
            c['value'],
            domain=c.get('domain', ''),
            path=c.get('path', '/'),
        )
    return session


# ============================================
# Supabase Helpers
# ============================================
def supabase_headers() -> dict:
    return {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
    }


def fetch_last_date() -> str | None:
    """Get the last date stored in Supabase (YYYY-MM-DD)."""
    try:
        resp = requests.get(
            f'{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=data&order=data.desc&limit=1',
            headers=supabase_headers(),
        )
        if resp.ok:
            records = resp.json()
            if records:
                return records[0]['data']
    except Exception as e:
        log.error('Error fetching last date: %s', e)
    return None


def upload_to_supabase(data: list) -> bool:
    """Upsert records to Supabase in batches."""
    if not data:
        log.info('No data to upload.')
        return True

    BATCH_SIZE = 500
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i : i + BATCH_SIZE]
        resp = requests.post(
            f'{SUPABASE_URL}/rest/v1/{TABLE_NAME}?on_conflict=data,protocolo',
            headers={
                **supabase_headers(),
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates,return=minimal',
            },
            json=batch,
        )
        if not resp.ok:
            log.error('Supabase upload failed (batch %d): %s', i // BATCH_SIZE + 1, resp.text)
            return False
        log.info('Uploaded batch %d (%d records)', i // BATCH_SIZE + 1, len(batch))

    return True


# ============================================
# HTML / XML Parsing
# ============================================
def extract_html_from_xajax(text: str) -> str | None:
    """Extract the HTML table from the xajax XML response."""
    html_content = None

    # Strategy 1: proper XML parsing
    try:
        root = ET.fromstring(text)
        for cmd in root.iter('cmd'):
            cmd_text = ''.join(cmd.itertext())
            if cmd.get('t') == 'resultado' and cmd_text:
                html_content = cmd_text
                break
        if not html_content:
            for cmd in root.iter('cmd'):
                cmd_text = ''.join(cmd.itertext())
                if cmd_text and '<table' in cmd_text.lower():
                    html_content = cmd_text
                    break
    except ET.ParseError:
        pass

    # Strategy 2: CDATA extraction
    if not html_content:
        m = re.search(r'<!\[CDATA\[(.*?)\]\]>', text, re.DOTALL)
        if m and '<table' in m.group(1).lower():
            html_content = m.group(1)

    # Strategy 3: regex fallback
    if not html_content:
        for m in re.finditer(r'<cmd[^>]*>(.*?)</cmd>', text, re.DOTALL):
            if '<table' in m.group(1).lower():
                html_content = m.group(1)
                break

    return html_content


def parse_table_rows(html: str) -> list[dict]:
    """Parse the HTML table into a list of record dicts (same schema as popup.js)."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if not table:
        return []

    rows = table.find_all('tr')
    records = []

    for row in rows:
        if row.find('th'):
            continue
        cells = row.find_all('td')
        if len(cells) < 13:
            continue

        def cell(idx):
            return cells[idx].get_text(strip=True) if idx < len(cells) else ''

        raw_date = cell(0)
        if not raw_date or raw_date.upper() == 'DATA' or 'total' in raw_date.lower():
            continue

        # DD/MM/YYYY → YYYY-MM-DD
        final_date = raw_date
        if '/' in raw_date:
            parts = raw_date.split('/')
            if len(parts) == 3:
                final_date = f'{parts[2]}-{parts[1]}-{parts[0]}'

        protocolo = cell(1)
        raw_placa = cell(3)
        placa = re.sub(r'[^a-zA-Z0-9]', '', raw_placa.split(',')[0]).upper()

        valor_str = cell(11).replace('R$', '').strip().replace('.', '').replace(',', '.')
        km_str = cell(12).replace('KM', '').strip().replace('.', '').replace(',', '.')

        def safe_float(s):
            try:
                return float(s) if s else 0.0
            except ValueError:
                return 0.0

        records.append({
            'data': final_date,
            'protocolo': protocolo,
            'placa': placa,
            'chassi': cell(4),
            'telefone_solicitante': cell(5),
            'beneficiario': cell(6),
            'telefone_beneficiario': cell(7),
            'situacao': cell(8),
            'motivo': cell(9),
            'servicos': cell(10),
            'valor': safe_float(valor_str),
            'km_total': safe_float(km_str),
        })

    return records


# ============================================
# Scraping (uses requests + saved cookies)
# ============================================
def scrape_report(session: requests.Session, start_date: str, end_date: str) -> dict:
    """
    Fetch and parse the attendance report.
    Returns: {'success': bool, 'data': list, 'session_expired': bool, 'error': str}
    """
    sd = datetime.strptime(start_date, '%Y-%m-%d')
    ed = datetime.strptime(end_date, '%Y-%m-%d')
    start_br = sd.strftime('%d/%m/%Y')
    end_br = ed.strftime('%d/%m/%Y')

    inner_query = (
        f'edtDataInicio={quote(start_br)}'
        f'&edtDataFinal={quote(end_br)}'
        f'&&&edtProtocolo=&edtPlaca=&&edtTelefoneSolicitante=&operadorTagsAtendimento=&'
    )
    xml_payload = f'<xjxquery><q>{inner_query}</q></xjxquery>'

    form_data = {
        'xajax': 'ConsultaAtendimento',
        'xajaxr': str(int(time.time() * 1000)),
        'xajaxargs[]': xml_payload,
    }

    try:
        resp = session.post(
            REPORT_URL,
            data=form_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
            },
        )

        if not resp.ok:
            return {'success': False, 'data': [], 'session_expired': False, 'error': f'HTTP {resp.status_code}'}

        text = resp.content.decode('iso-8859-1')

        # Session-expired heuristic (same as popup.js)
        if len(text) < 100 or 'login' in text.lower() or 'sessao' in text.lower():
            return {'success': False, 'data': [], 'session_expired': True, 'error': 'Session expired'}

        html_content = extract_html_from_xajax(text)
        if not html_content:
            return {'success': False, 'data': [], 'session_expired': False, 'error': 'No HTML content found in response'}

        records = parse_table_rows(html_content)
        return {'success': True, 'data': records, 'session_expired': False, 'error': ''}

    except Exception as e:
        return {'success': False, 'data': [], 'session_expired': False, 'error': str(e)}


# ============================================
# Login via Playwright (handles reCAPTCHA v3)
# ============================================
STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
    window.chrome = { runtime: {} };
"""


async def perform_login(headless: bool = True) -> list:
    """
    Open a real Chromium browser, fill credentials, click login.
    reCAPTCHA v3 runs invisibly via the site's own JS.
    Returns the browser cookies on success.
    """
    from playwright.async_api import async_playwright

    mode = 'headless' if headless else 'headful'
    log.info('Starting Playwright login (%s)...', mode)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ],
        )

        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            locale='pt-BR',
        )
        await context.add_init_script(STEALTH_JS)

        page = await context.new_page()

        # Load login page
        await page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
        log.info('Login page loaded')

        # Fill credentials
        await page.fill('#edtLogin', INFORNET_LOGIN)
        await page.fill('#edtSenha', INFORNET_PASSWORD)
        await page.wait_for_timeout(800)
        log.info('Credentials entered')

        # Click the ACESSAR button — the site's JS triggers reCAPTCHA v3 + xajax_CheckUser
        await page.click('button.btn-logon')
        log.info('Login button clicked — waiting for reCAPTCHA v3 & server response...')

        # Wait for redirect (xajax_CheckUser → server validates → redirects to home.php)
        login_ok = False
        try:
            await page.wait_for_url(re.compile(r'home\.php'), timeout=20000)
            login_ok = True
            log.info('Login successful — redirected to home.php')
        except Exception:
            # Redirect might not happen; verify by navigating to report page
            log.info('No redirect detected, verifying session...')

        if not login_ok:
            # Check if reCAPTCHA v2 was triggered
            v2_visible = await page.evaluate(
                "document.querySelector('.g-recaptchatoken-recaptch-v2')?.style.display !== 'none'"
            )
            if v2_visible and headless:
                log.warning('reCAPTCHA v2 triggered — retrying in headful mode...')
                await browser.close()
                return await perform_login(headless=False)

            # Try accessing the report page directly to verify the session
            await page.goto(REPORT_URL, wait_until='networkidle', timeout=15000)
            page_text = await page.content()
            if 'ConsultaAtendimento' in page_text or 'edtDataInicio' in page_text:
                login_ok = True
                log.info('Login verified — report page accessible')
            else:
                log.error('Login appears to have failed. Page URL: %s', page.url)

        cookies = await context.cookies()
        await browser.close()

        if not login_ok:
            log.error('Could not confirm login success')
        return cookies


# ============================================
# Log Management & Email Alerts
# ============================================
def cleanup_old_logs(keep_days: int = 7):
    """Delete log files older than keep_days from the logs directory."""
    cutoff = datetime.now() - timedelta(days=keep_days)
    for log_file in LOGS_DIR.glob('scraper_*.log'):
        try:
            date_str = log_file.stem.replace('scraper_', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if file_date < cutoff:
                log_file.unlink()
                log.info('Deleted old log: %s', log_file.name)
        except (ValueError, OSError):
            pass


def send_alert_email(subject: str, body: str):
    """Send an alert email with log files attached to all ALERT_EMAILS recipients."""
    if not SMTP_USER or not SMTP_PASSWORD or not ALERT_EMAILS:
        log.warning('Email not configured — skipping alert: %s', subject)
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = ', '.join(ALERT_EMAILS)
        msg['Subject'] = f'[MaisVantagens Scraper] {subject}'

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Attach all recent log files (last 7 days)
        for lf in sorted(LOGS_DIR.glob('scraper_*.log')):
            try:
                part = MIMEBase('application', 'octet-stream')
                with open(lf, 'rb') as f:
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition', f'attachment; filename="{lf.name}"'
                )
                msg.attach(part)
            except OSError:
                pass

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ALERT_EMAILS, msg.as_string())

        log.info('Alert email sent to: %s', ', '.join(ALERT_EMAILS))
    except Exception as e:
        log.error('Failed to send alert email: %s', e)


def check_stale_data() -> bool:
    """Return True if the last DB record is older than STALE_DATA_DAYS."""
    last_date = fetch_last_date()
    if not last_date:
        return True

    last_dt = datetime.strptime(last_date, '%Y-%m-%d')
    days_behind = (datetime.now() - last_dt).days

    if days_behind >= STALE_DATA_DAYS:
        log.warning(
            'Data is stale: last record is %d days old (%s)', days_behind, last_date
        )
        return True
    return False


# ============================================
# Main Orchestration
# ============================================
async def run():
    cleanup_old_logs()

    log.info('=' * 60)
    log.info('Scraper run started at %s', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log.info('=' * 60)

    # Validate env
    missing = []
    if not INFORNET_LOGIN:
        missing.append('INFORNET_LOGIN')
    if not INFORNET_PASSWORD:
        missing.append('INFORNET_PASSWORD')
    if not SUPABASE_URL:
        missing.append('SUPABASE_URL')
    if not SUPABASE_ANON_KEY:
        missing.append('SUPABASE_ANON_KEY')
    if missing:
        log.error('Missing env vars: %s — check your .env file', ', '.join(missing))
        sys.exit(1)

    # 1. Determine date range
    last_date = fetch_last_date()
    today = datetime.now().strftime('%Y-%m-%d')

    if last_date:
        start_dt = datetime.strptime(last_date, '%Y-%m-%d') - timedelta(days=1)
        start_date = start_dt.strftime('%Y-%m-%d')
        log.info('Last DB date: %s  →  scraping from: %s to %s', last_date, start_date, today)
    else:
        start_date = today
        log.info('DB empty — scraping today only: %s', today)

    end_date = today

    # 2. Try with saved cookies first
    cookies = load_cookies()
    result = None

    if cookies:
        session = cookies_to_session(cookies)
        result = scrape_report(session, start_date, end_date)

        if result['session_expired']:
            log.info('Session expired — will re-login')
            cookies = []
            result = None
        elif not result['success']:
            log.warning('Scrape failed with saved cookies: %s', result['error'])
            cookies = []
            result = None

    # 3. Login if needed and retry
    if not cookies or result is None:
        log.info('Performing fresh login...')
        cookies = await perform_login(headless=True)
        save_cookies(cookies)

        session = cookies_to_session(cookies)
        result = scrape_report(session, start_date, end_date)

        # If still failing after fresh login, try headful as last resort
        if result['session_expired'] or not result['success']:
            log.warning('Headless login did not yield valid session. Trying headful...')
            cookies = await perform_login(headless=False)
            save_cookies(cookies)

            session = cookies_to_session(cookies)
            result = scrape_report(session, start_date, end_date)

    # 4. Final result check
    if not result['success']:
        log.error('Scraping failed: %s', result['error'])
        send_alert_email(
            'Scraping Failed',
            f'The scraper failed to retrieve data.\n\n'
            f'Error: {result["error"]}\n'
            f'Date range: {start_date} to {end_date}\n'
            f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n'
            f'Log files are attached for review.',
        )
        sys.exit(1)

    log.info('Scraped %d records', len(result['data']))

    # 5. Upload
    if result['data']:
        if upload_to_supabase(result['data']):
            log.info('Upload complete — %d records upserted', len(result['data']))
        else:
            log.error('Upload to Supabase failed')
            send_alert_email(
                'Upload to Supabase Failed',
                f'The scraper retrieved {len(result["data"])} records but failed to upload.\n\n'
                f'Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n'
                f'Log files are attached for review.',
            )
            sys.exit(1)
    else:
        log.info('No new records to upload — database is up to date')

    # 6. Check for stale data (no new records in STALE_DATA_DAYS days)
    if check_stale_data():
        last = fetch_last_date() or 'N/A'
        send_alert_email(
            f'No New Records for {STALE_DATA_DAYS}+ Days',
            f'The last record in the database is dated {last}.\n'
            f'No new records have appeared for at least {STALE_DATA_DAYS} days.\n\n'
            f'Today: {datetime.now().strftime("%Y-%m-%d")}\n\n'
            f'This may indicate the source website has no new data, '
            f'or there is an issue with scraping.\n\n'
            f'Log files are attached for review.',
        )

    log.info('Run finished successfully')


if __name__ == '__main__':
    asyncio.run(run())
