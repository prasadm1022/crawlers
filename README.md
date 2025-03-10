# web scrapers

web scrapers for day to day tasks...

**Riyasewana.com Ad Alerts**

- This is a Python-based web scraper that monitors riyasewana.com for new vehicle listings and sends email alerts
  when new posts are detected.
- Features:
    - Uses Selenium to extract new listings.
    - Stores previously detected posts to avoid duplicate alerts.
    - Sends automated email notifications via SMTP.
    - Runs on a scheduled interval using schedule.
    - Configure environment variables in ".env" file as you prefer.
- How to run:
    - Install dependencies using `pip install -r requirements.txt` command.
    - Execute `python riyasewana_ad_alerts.py` command to run the script.
    - Use `DockerFile` for docker execution.