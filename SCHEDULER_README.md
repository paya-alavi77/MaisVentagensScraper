# MaisVantagens Scraper - Local Mac Scheduler

The scraper is now configured to run automatically on your Mac at the following times (UTC-3):
- **01:00** (1 AM)
- **06:00** (6 AM)
- **10:00** (10 AM)
- **13:00** (1 PM)
- **17:00** (5 PM)
- **20:00** (8 PM)

## How It Works

The scheduler uses macOS's built-in `launchd` service, which is more reliable than cron on Mac. The configuration file is located at:
```
~/Library/LaunchAgents/com.maisvantagens.scraper.plist
```

## Managing the Scheduler

### Check if the scheduler is running:
```bash
launchctl list | grep maisvantagens
```

### View detailed scheduler status:
```bash
launchctl print gui/$(id -u)/com.maisvantagens.scraper
```

### Stop the scheduler:
```bash
launchctl unload ~/Library/LaunchAgents/com.maisvantagens.scraper.plist
```

### Start the scheduler:
```bash
launchctl load ~/Library/LaunchAgents/com.maisvantagens.scraper.plist
```

### Restart the scheduler (after making changes):
```bash
launchctl unload ~/Library/LaunchAgents/com.maisvantagens.scraper.plist
launchctl load ~/Library/LaunchAgents/com.maisvantagens.scraper.plist
```

### Run the scraper manually (for testing):
```bash
cd ~/MaisVentagensScraper
python3 scraper.py
```

## Logs

The scraper creates daily log files in the `logs/` directory:
- **Daily logs**: `logs/scraper_YYYY-MM-DD.log`
- **Launchd output**: `logs/launchd.log`
- **Launchd errors**: `logs/launchd.error.log`

Logs older than 7 days are automatically deleted.

## Email Alerts

The scraper will send email alerts to the addresses configured in `.env` (ALERT_EMAILS) when:
1. Scraping fails
2. Upload to Supabase fails
3. No new records have been added for 4+ days

## Important Notes

- **Your Mac must be awake** for the scheduler to run. If your Mac is asleep at a scheduled time, the job will NOT run.
- The scheduler will automatically start when you log in to your Mac.
- If you restart your Mac, the scheduler will automatically reload.
- Make sure your `.env` file is properly configured with all credentials.

## Troubleshooting

### Scheduler not running?
```bash
# Check if it's loaded
launchctl list | grep maisvantagens

# If not loaded, load it
launchctl load ~/Library/LaunchAgents/com.maisvantagens.scraper.plist
```

### Check recent runs:
```bash
# View today's log
cat logs/scraper_$(date +%Y-%m-%d).log

# View launchd output
tail -50 logs/launchd.log
```

### Test manually:
```bash
cd ~/MaisVentagensScraper
python3 scraper.py
```

### Force a run right now (for testing):
```bash
launchctl start com.maisvantagens.scraper
```
