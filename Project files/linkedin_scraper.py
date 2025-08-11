# linkedin_scraper.py
"""
Robust LinkedIn scraper using Selenium + webdriver-manager.

Notes:
- Put your LINKEDIN_EMAIL and LINKEDIN_PASSWORD in a .env file (see .env.example).
- For initial debugging set HEADLESS=False so you can watch login / 2FA.
- If Chrome isn't found automatically, set CHROME_BINARY env var to the chrome executable path.
"""

import os
import time
import json
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# webdriver-manager to auto-download chromedriver
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Env config
EMAIL = os.environ.get("LINKEDIN_EMAIL")
PASSWORD = os.environ.get("LINKEDIN_PASSWORD")
OUTPUT_JSON = os.environ.get("OUTPUT_JSON_PATH", "scraped_profile.json")
HEADLESS = os.environ.get("HEADLESS", "True").lower() in ["true", "1", "yes"]
CHROME_BINARY = os.environ.get("CHROME_BINARY", None)

def _find_chrome_binary():
    """Try to locate Chrome/Chromium binary on common locations (Windows/Linux/Mac)."""
    if CHROME_BINARY:
        if os.path.exists(CHROME_BINARY):
            return CHROME_BINARY
        logging.warning("CHROME_BINARY set but path not found: %s", CHROME_BINARY)

    # Common Windows paths
    potential = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Chromium\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]
    for p in potential:
        if os.path.exists(p):
            return p
    return None

def create_driver(headless=True, implicit_wait=8):
    """Create Selenium Chrome driver using webdriver-manager Service wrapper."""
    chrome_options = Options()

    # Headless options - use either modern headless or fallback
    try:
        if headless:
            chrome_options.add_argument("--headless=new")
        else:
            # helpful for debugging
            chrome_options.add_argument("--start-maximized")
    except Exception:
        # fallback
        if headless:
            chrome_options.add_argument("--headless")

    # Common options to reduce detection
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--window-size=1200,900")
    # sensible user-agent to look like a normal browser
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )

    # set chrome binary if we can find it
    chrome_bin = _find_chrome_binary()
    if chrome_bin:
        logging.info("Using Chrome binary: %s", chrome_bin)
        chrome_options.binary_location = chrome_bin
    else:
        logging.warning("Chrome binary not found automatically. If driver fails to start, set CHROME_BINARY env var to chrome executable path.")

    # try to construct Service and driver
    try:
        service = Service(ChromeDriverManager().install())
    except Exception as e:
        logging.error("Failed to install/start chromedriver via webdriver_manager: %s", e)
        raise

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(implicit_wait)
        return driver
    except Exception as e:
        logging.error("Failed to start Chrome WebDriver: %s", e)
        # include hint for common causes
        logging.error("Common causes: Chrome not installed, version mismatch, path issues, or insufficient permissions.")
        raise

def linkedin_login(driver):
    """Login to LinkedIn using credentials from .env"""
    if not EMAIL or not PASSWORD:
        raise EnvironmentError("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file.")

    driver.get("https://www.linkedin.com/login")
    wait = WebDriverWait(driver, 20)
    try:
        email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_input = driver.find_element(By.ID, "password")
        email_input.clear()
        email_input.send_keys(EMAIL)
        password_input.clear()
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.RETURN)
        # Wait for an element on the logged-in homepage (search box) or profile top nav
        try:
            wait.until(EC.presence_of_element_located((By.ID, "global-nav-search")))
            logging.info("Logged in successfully (search box detected).")
        except Exception:
            # fallback wait briefly for potential redirections or 2FA
            logging.info("Login submitted — waiting a few seconds for redirection or 2FA.")
            time.sleep(5)
    except Exception as e:
        logging.error("Login flow failed: %s", e)
        raise

def scrape_profile(driver, profile_url):
    """Open given LinkedIn profile URL and attempt to extract basic fields and recent posts."""
    driver.get(profile_url)
    wait = WebDriverWait(driver, 12)
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
    except Exception:
        # continue even if wait fails; page may still have partial content
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # header info with fallbacks
    def text_of(sel):
        return sel.get_text(strip=True) if sel else None

    name = text_of(soup.select_one("li.inline.t-24.t-black.t-normal.break-words") or soup.select_one("h1"))
    headline = text_of(soup.select_one("h2.mt1.t-18.t-black.t-normal") or soup.select_one("div.text-body-medium.break-words"))
    location = text_of(soup.select_one("li.t-16.t-black.t-normal.inline-block") or soup.select_one("span.text-body-small.inline.t-black--light.break-words"))

    # experiences
    experiences = []
    # try experience section
    exp_section = soup.find("section", {"id": "experience-section"}) or soup.find(attrs={"data-section": "experience"})
    if exp_section:
        items = exp_section.select("li")
        for it in items:
            title = text_of(it.select_one("h3"))
            company = text_of(it.select_one("p.pv-entity__secondary-title") or it.select_one("span.pv-entity__secondary-title"))
            date_range = text_of(it.select_one("h4.pv-entity__date-range span:nth-child(2)") or it.select_one("span.pv-entity__date-range"))
            summary = text_of(it.select_one("p.pv-entity__description"))
            experiences.append({"title": title, "company": company, "date_range": date_range, "summary": summary})
    else:
        # fallback: generic li items with h3
        for it in soup.select("li"):
            title_sel = it.select_one("h3")
            if title_sel:
                title = text_of(title_sel)
                company = text_of(it.select_one("span.pv-entity__secondary-title"))
                date_range = text_of(it.select_one("h4 span"))
                summary = text_of(it.select_one("p"))
                experiences.append({"title": title, "company": company, "date_range": date_range, "summary": summary})

    # education
    educations = []
    edu_section = soup.find("section", {"id": "education-section"})
    if edu_section:
        for it in edu_section.select("li"):
            school = text_of(it.select_one("h3"))
            degree = text_of(it.select_one(".pv-entity__degree-name .pv-entity__comma-item"))
            field = text_of(it.select_one(".pv-entity__fos .pv-entity__comma-item"))
            date_range = text_of(it.select_one(".pv-entity__dates time"))
            educations.append({"school": school, "degree": degree, "field": field, "date_range": date_range})

    # skills (several possible selectors)
    skills = []
    for sel in soup.select(".pv-skill-category-entity__name, .skill-pill, .pv-skill-entity__skill-name"):
        s = text_of(sel)
        if s:
            skills.append(s)

    # recent posts: visit activity/shares page
    posts = []
    try:
        activity_url = profile_url.rstrip("/") + "/recent-activity/shares/"
        driver.get(activity_url)
        time.sleep(2)
        soup2 = BeautifulSoup(driver.page_source, "html.parser")
        for p in soup2.select("div.occludable-update")[:10]:
            text_elem = p.select_one(".feed-shared-update-v2__description, .feed-shared-text__text-view, .update-components-text")
            date_elem = p.select_one("span.feed-shared-actor__sub-description > span.visually-hidden")
            posts.append({"text": text_elem.get_text(strip=True) if text_elem else None, "date": date_elem.get_text(strip=True) if date_elem else None})
    except Exception:
        # silently continue if we cannot access activity
        posts = []

    profile = {
        "name": name,
        "headline": headline,
        "location": location,
        "experiences": experiences,
        "educations": educations,
        "skills": skills,
        "posts": posts,
        "profile_url": profile_url
    }
    return profile

def main(profile_url):
    driver = None
    try:
        logging.info("Starting Chrome WebDriver (headless=%s)", HEADLESS)
        driver = create_driver(headless=HEADLESS)
        logging.info("Logging into LinkedIn...")
        linkedin_login(driver)
        logging.info("Scraping profile: %s", profile_url)
        scraped = scrape_profile(driver, profile_url)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(scraped, f, indent=2, ensure_ascii=False)
        logging.info("Saved scraped data -> %s", OUTPUT_JSON)
    except Exception as e:
        logging.exception("Error during scraping: %s", e)
        # write a small error json so caller can see failure details (optional)
        err_obj = {"error": str(e)}
        try:
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(err_obj, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python linkedin_scraper.py <linkedin_profile_url>")
        sys.exit(1)
    profile_url = sys.argv[1]
    main(profile_url)

