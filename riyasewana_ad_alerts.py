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

import csv
import os
import smtplib
import ssl
import schedule
import time

# Email generation related imports
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# If using python-dotenv
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Email Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")  # Use app-specific password if using Gmail
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Crawler Settings
WEB_PAGE_URLS = os.getenv("WEB_PAGE_URL").split(",")
POST_SELECTOR = os.getenv("POST_SELECTOR")

# Known Posts CSV File (as an alternative, "SQLite" database can be used)
KNOWN_POSTS_CSV_FILE = os.getenv("KNOWN_POSTS_CSV_FILE")


def setup_driver():
    """
    Set up the Selenium WebDriver with popup blocking.
    """
    print("Setup selenium driver...")

    chrome_options = Options()

    chrome_options.add_argument("--headless")  # Run without opening a window
    chrome_options.add_argument("--disable-popup-blocking")  # Block popups
    chrome_options.add_argument("--disable-notifications")  # Block notifications
    chrome_options.add_argument("--disable-javascript")  # Optional: Disable JavaScript if not needed
    chrome_options.add_argument("--no-sandbox")  # Avoid issues in some environments
    chrome_options.add_argument("--disable-dev-shm-usage")  # Prevent crashes in Docker/Linux

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


def get_known_posts():
    """
    Read known posts from a CSV file.
    """
    print("Load old data from csv...")

    if not os.path.exists(KNOWN_POSTS_CSV_FILE):
        return set()

    with open(KNOWN_POSTS_CSV_FILE, newline='', encoding="utf-8") as file:
        reader = csv.reader(file)
        return set(row[0] for row in reader)  # Assuming first column stores post titles


def save_new_posts(new_posts):
    """
    Append new posts to the CSV file.
    """
    print("Save new data to csv...")

    with open(KNOWN_POSTS_CSV_FILE, "a", newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(new_posts)


def check_new_posts():
    """
    Fetch webpage using Selenium, check for new posts, and send alerts.
    """
    print("Checking for new posts...")

    # Initialize WebDriver
    driver = setup_driver()

    try:
        for url in WEB_PAGE_URLS:
            print(f"Checking website: {url}")

            # Open the page
            driver = setup_driver()
            driver.get(url.strip())
            time.sleep(3)  # Allow time for JavaScript content to load

            # Extract posts using Selenium
            posts = driver.find_elements(By.CLASS_NAME, POST_SELECTOR)
            if not posts:
                print("No posts found or the structure may have changed...")
                continue

            known_posts = get_known_posts()
            new_posts_found = []

            for post in posts:
                link_tag = post.find_element(By.TAG_NAME, "a")
                post_title = link_tag.text.strip()
                post_link = link_tag.get_attribute("href")

                unique_id = post_link.strip()
                if unique_id not in known_posts:
                    new_posts_found.append((unique_id, post_title))

            if new_posts_found:
                print(f"Found {len(new_posts_found)} new post(s)")
                save_new_posts(new_posts_found)
                send_email_alert(new_posts_found, url)
            else:
                print("No new posts at this time")

    except Exception as e:
        print(f"Error during crawling: {e}")
    finally:
        driver.quit()  # Ensure the browser is closed


def send_email_alert(new_posts, website_url):
    """
    Sends an email with the list of new posts.
    """
    print("Sending email alert...")

    message = MIMEMultipart("alternative")
    message["Subject"] = "New Civic FD1 Posts Detected"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    # Create the HTML body for the email
    html_body = f"<h3>New posts found on <a href='{website_url}'>{website_url}</a></h3><ul>"
    for link, title in new_posts:
        html_body += f"<li><a href='{link}'>{title}</a></li>"
    html_body += "</ul>"

    part = MIMEText(html_body, "html")
    message.attach(part)

    # Secure connection with SMTP server
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        try:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            print(f"Email sent successfully for {website_url}.")
        except Exception as e:
            print(f"Error sending email for {website_url}: {e}")


def main():
    # Schedule the job to run every hour
    schedule.every(1).hours.do(check_new_posts)

    # Run once at startup as well
    check_new_posts()

    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
