# Copyright 2025 Prasad Madusanka Basnayaka
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import concurrent.futures
import os
import smtplib
import sqlite3
import ssl
import time
import psutil
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as Ec
from selenium.webdriver.support.wait import WebDriverWait

# Load environment variables from the .env file
load_dotenv()

# Email Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")  # Use app-specific password if using Gmail
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
# Scraper Settings
WEB_PAGE_URLS = os.getenv("WEB_PAGE_URL").split(",")
WEB_PAGE_URL_SUBJECTS = os.getenv("WEB_PAGE_URL_SUBJECT").split(",")
POST_SELECTOR = os.getenv("POST_SELECTOR")
SCRAPER_FREQUENCY_MINUTES = int(os.getenv("SCRAPER_FREQUENCY_MINUTES"))
# SQLite DB to store known posts
KNOWN_POSTS_DATABASE = "riyasewana_ad_alerts.db"

# Configure logger to print to both console and file
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
# Log file handler (saves to file)
file_handler = logging.FileHandler("riyasewana_ad_alerts.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_formatter)
# Log console handler (prints in terminal)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)
# Configure the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_available_threads():
    """
    Get the number of available CPU threads
    """
    logger.info("getting available cpu threads...")

    total_cores = os.cpu_count()  # Get total CPU cores
    cpu_usage = psutil.cpu_percent(interval=1, percpu=True)  # CPU usage per core
    idle_cores = sum(1 for usage in cpu_usage if usage < 20)  # Count idle cores (<20% usage)

    logger.info(f"\nusage={cpu_usage}\ntotal={total_cores}\navailable={idle_cores}")

    # Fallback to 1 if none is available
    return max(1, idle_cores)


def setup_database():
    """
    Initialize SQLite database for storing known posts.
    """
    logger.info("setup SQLite database...")

    try:
        with sqlite3.connect(KNOWN_POSTS_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posts ( id TEXT PRIMARY KEY, title TEXT )
                """
            )
            conn.commit()
    except Exception as e:
        raise Exception(f"error setup database [{e}]")


def setup_driver():
    """
    Set up the Selenium WebDriver with popup blocking.
    """
    logger.info("setup selenium driver...")

    try:
        chrome_options = Options()

        chrome_options.add_argument("--headless")  # Run without opening a window
        chrome_options.add_argument("--no-sandbox")  # Avoid issues in some environments
        chrome_options.add_argument("--disable-popup-blocking")  # Block popups
        chrome_options.add_argument("--disable-notifications")  # Block notifications
        chrome_options.add_argument("--disable-javascript")  # Optional: Disable JavaScript if not needed
        chrome_options.add_argument("--disable-gpu")  # Disable GPU rendering
        chrome_options.add_argument("--disable-dev-shm-usage")  # Prevent crashes in Docker/Linux
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid bot detection

        # Block JavaScript, images, popups, and ads
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,  # Disable images
                "javascript": 2,  # Disable JavaScript
                "popups": 2,  # Block popups
                "ads": 2  # Block ads (Chrome experimental feature)
            }
        }
        chrome_options.add_experimental_option("prefs", prefs)

        return webdriver.Chrome(options=chrome_options)
    except Exception as e:
        raise Exception(f"error setup driver [{e}]")


def get_known_posts():
    """
    Retrieve known posts from SQLite database.
    """
    logger.info("retrieving known posts from database...")

    try:
        with sqlite3.connect(KNOWN_POSTS_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM posts")
            return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        raise Exception(f"error getting known posts [{e}]")


def save_new_posts(new_posts):
    """
    Save new posts to SQLite database.
    """
    logger.info("saving new posts to database...")

    try:
        with sqlite3.connect(KNOWN_POSTS_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.executemany("INSERT OR IGNORE INTO posts (id, title) VALUES ( ?, ? )", new_posts)
            conn.commit()
    except Exception as e:
        raise Exception(f"error saving new posts [{e}]")


def check_new_posts(new_posts, known_posts, website_url, website_subject):
    """
    Fetch webpage using Selenium, check for new posts, and send alerts.
    """
    logger.info(f"{website_subject} :: checking new posts...")

    # Initialize WebDriver
    try:
        driver = setup_driver()
    except Exception as e:
        logger.error(f"{website_subject} :: {e}")
        return

    try:
        driver.get(website_url.strip())  # Open the page

        # Wait until posts are loaded
        try:
            posts = WebDriverWait(driver, 10).until(Ec.presence_of_all_elements_located((By.CLASS_NAME, POST_SELECTOR)))
        except Exception as e:
            raise Exception(f"error fetching posts [{e}]")

        found_posts = []

        # Extract post details
        for post in posts:
            try:
                link_tag = post.find_element(By.TAG_NAME, "a")
                post_title = link_tag.text.strip()
                post_link = link_tag.get_attribute("href")
                unique_id = post_link.strip()
                if unique_id not in known_posts:
                    found_posts.append((unique_id, post_title))
            except Exception:
                continue

        if found_posts:
            logger.info(f"{website_subject} :: found {len(found_posts)} new post(s)")
            new_posts[website_subject] = (website_url, found_posts)
        else:
            raise Exception("no posts found")
    except Exception as e:
        logger.error(f"{website_subject} :: {e}")
    finally:
        driver.quit()  # Quit WebDriver


def send_email_alert(new_posts):
    """
    Sends an email with the list of new posts.
    """
    logger.info("sending email alert...")

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = "Riyasewana Posts Alert"
        message["From"] = SENDER_EMAIL
        message["To"] = RECEIVER_EMAIL

        html_body = "<h3>New posts detected :</h3>"
        for website_subject, (website_url, posts) in new_posts.items():
            html_body += f"<h4>{website_subject} (<a href='{website_url}'>Link</a>)</h4><ul>"
            for link, title in posts:
                html_body += f"<li><a href='{link}'>{title}</a></li>"
            html_body += "</ul>"
        message.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            logger.info("email sent successfully")
        except Exception as e:
            raise Exception(f"{e}")
    except Exception as e:
        raise Exception(f"error sending email [{e}]")


def run_parallel_scraping():
    """
    Run web scraping in parallel using threading.
    """
    logger.info("starting scrape process...")

    known_posts = get_known_posts()  # Get known posts
    new_posts = {}

    # Scraping & wait for results
    with concurrent.futures.ThreadPoolExecutor(max_workers=get_available_threads()) as executor:
        futures = [
            executor.submit(check_new_posts, new_posts, known_posts, url, subject)
            for url, subject in zip(WEB_PAGE_URLS, WEB_PAGE_URL_SUBJECTS)
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # Wait for completion

    if new_posts:
        save_new_posts([post for _, posts in new_posts.values() for post in posts])  # Save new posts
        send_email_alert(new_posts)  # Send email alert for new posts
    else:
        logger.info("no new posts at this time")


def main():
    try:
        setup_database()  # Setup database

        # Run scraper at the defined frequency
        while True:
            try:
                run_parallel_scraping()
                time.sleep(SCRAPER_FREQUENCY_MINUTES * 60)
            except Exception as e:
                logger.error(f"{e}")
    except KeyboardInterrupt:
        logger.warning("Stopping the scraper...")


if __name__ == "__main__":
    main()
