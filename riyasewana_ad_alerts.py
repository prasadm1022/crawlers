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

import os
import requests
import smtplib
import ssl
import schedule
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Global variable to store known post IDs or titles
known_posts = set()

# Email Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "default_sender")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "default_password")  # Use app-specific password if using Gmail
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "default_receiver")

# Crawler Settings
WEB_PAGE_URL = os.getenv("WEB_PAGE_URL", "default_website")
POST_SELECTOR = os.getenv("POST_SELECTOR", "default_selector")

# Load environment variables from the .env file
load_dotenv()  # By default, it looks for a file named ".env" in the current directory


def check_new_posts():
    """
    Fetch the webpage, parse for posts, compare with known posts, and send alerts if any are new.
    """
    print("Checking for new posts...")

    try:
        # 1. Fetch the page
        response = requests.get(WEB_PAGE_URL)
        response.raise_for_status()  # Raise an error for bad status
    except Exception as e:
        print(f"Error fetching the page: {e}")
        return

    # 2. Parse the HTML
    soup = BeautifulSoup(response.text, 'html.parser')

    # 3. Extract posts
    #    (Depending on the page structure, you’ll need to customize these selectors)
    #    each post is within a container <div class="example-div">,
    #    and each div has a link <a> with a href or text that identifies it uniquely.
    posts = soup.select(POST_SELECTOR)

    if not posts:
        print("No posts found or the HTML structure may have changed.")
        return

    new_posts_found = []

    for post in posts:
        # Example: get a post title or unique ID
        link_tag = post.find('a')
        if link_tag:
            post_title = link_tag.get_text(strip=True)
            post_link = link_tag.get('href')

            # Create a unique identifier (could be the combination of title + link)
            unique_id = (post_title + (post_link or '')).strip()

            if unique_id not in known_posts:
                known_posts.add(unique_id)
                new_posts_found.append((post_title, post_link))

    # If we have new posts, send an email
    if new_posts_found:
        print(f"Found {len(new_posts_found)} new post(s). Sending email alert...")
        send_email_alert(new_posts_found)
    else:
        print("No new posts at this time.")


def send_email_alert(new_posts):
    """
    Sends an email with the list of new posts.
    """
    message = MIMEMultipart("alternative")
    message["Subject"] = "New Civic FD1 Posts Detected"
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    # Create the HTML body for the email
    html_body = "<h3>New posts found on riyasewana.com</h3><ul>"
    for title, link in new_posts:
        # If link is relative, you might need to prepend the domain: "https://riyasewana.com" + link
        full_link = link if link.startswith("http") else "https://riyasewana.com" + link
        html_body += f"<li><a href='{full_link}'>{title}</a></li>"
    html_body += "</ul>"

    part = MIMEText(html_body, "html")
    message.attach(part)

    # Secure connection with SMTP server
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        try:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
            print("Email sent successfully.")
        except Exception as e:
            print(f"Error sending email: {e}")


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
