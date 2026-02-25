#!/bin/bash
# ============================================
# Cron Setup for MaisVantagens Scraper
# Schedule: 06:00, 10:00, 13:00, 17:00, 20:00, 01:00
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
SCRAPER="$SCRIPT_DIR/scraper.py"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "ERROR: Python venv not found at $PYTHON_BIN"
    echo "Run the setup first:"
    echo "  cd $SCRIPT_DIR"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  playwright install chromium"
    exit 1
fi

CRON_JOB="0 1,6,10,13,17,20 * * * $PYTHON_BIN $SCRAPER >> $SCRIPT_DIR/scraper.log 2>&1"

# Check if job already exists
EXISTING=$(crontab -l 2>/dev/null | grep -F "$SCRAPER")

if [ -n "$EXISTING" ]; then
    echo "Cron job already exists. Replacing..."
    crontab -l 2>/dev/null | grep -v -F "$SCRAPER" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job installed:"
echo "  $CRON_JOB"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "The scraper will run at: 01:00, 06:00, 10:00, 13:00, 17:00, 20:00 (system timezone)"
