"""Career Cortex - Wellfound Job Scraper"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import mysql.connector
import re

from config import settings

# Configuration constants
WELLFOUND_URL = "https://wellfound.com/jobs"
SCROLL_PAUSE_TIME = settings.SCROLL_PAUSE_TIME
MAX_SCROLLS = settings.MAX_SCROLLS


def get_db_connection():
    """Establish database connection with utf8mb4 support for emojis/special chars"""
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset=settings.DB_CHARSET,
        collation=f"{settings.DB_CHARSET}_unicode_ci"
    )


def clean_wellfound_text(raw_text):
    """
    Clean whitespace without destroying sentence structure.
    """
    if not raw_text:
        return ""
    
    # Replace multiple newlines/spaces with a single space
    cleaned = " ".join(raw_text.split())
    return cleaned

def extract_meta_data(soup, page_title):
    """
    Helper to extract Company, Location and Remote status
    """
    company = "Unknown"
    location = "Unknown"
    is_remote = 0
    
    # 1. Try to extract Company from Page Title (Format: "Role at Company - ...")
    if " at " in page_title:
        try:
            parts = page_title.split(" at ")
            if len(parts) > 1:
                # Take the part after "at", and split by " - " or "|" if present
                company_part = parts[1].split("-")[0].split("|")[0]
                company = company_part.strip()
        except:
            pass

    # 2. Extract Location & Remote status from text analysis
    # (Since classes change, we scan the text for keywords)
    full_text = soup.get_text().lower()
    
    if "remote" in full_text:
        is_remote = 1
        # If it's explicitly remote, we can set location to Remote
        if location == "Unknown":
            location = "Remote"
            
    return company, location, is_remote

def scrape_wellfound():
    print("Starting Wellfound scraper...")

    options = Options()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10) # 10 second timeout handler

    # --- Login Phase ---
    driver.get("https://wellfound.com/login")
    print("\n" + "=" * 50)
    print("Manual login required:")
    print("1. Log into Wellfound")
    print("2. Navigate to the Jobs page")
    print("3. Press ENTER here when ready...")
    print("=" * 50 + "\n")
    input("Press ENTER to continue...")

    try:
        # Re-verify window handle
        if not driver.window_handles:
            print("Error: Browser closed.")
            return
        driver.switch_to.window(driver.window_handles[-1])
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # --- Scrolling Phase ---
    print("Loading jobs...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for i in range(MAX_SCROLLS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Robust "Show More" clicking
        try:
            # Look for button by distinct text or structure
            show_more = driver.find_elements(By.XPATH, "//button[contains(text(), 'Show more') or contains(text(), 'Load more')]")
            if show_more:
                driver.execute_script("arguments[0].click();", show_more[0])
                time.sleep(2)
        except Exception:
            pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        print(f"Scroll {i+1}/{MAX_SCROLLS}")

    # --- Link Extraction ---
    print("Parsing HTML...")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    job_links = []
    processed_urls = set()
    
    target_roles = ["engineer", "developer", "backend", "frontend", "full stack", "python", "ai", "machine learning", "data"]

    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if "/jobs/" not in href: continue
        
        full_url = f"https://wellfound.com{href}" if not href.startswith("http") else href.split('?')[0]
        
        if full_url in processed_urls: continue
        
        title = link.get_text(strip=True)
        if not title: continue
        
        if any(role in title.lower() for role in target_roles):
            processed_urls.add(full_url)
            job_links.append((title, full_url))

    print(f"Found {len(job_links)} target jobs.")

    # --- Detail Extraction & DB Save ---
    conn = get_db_connection()
    cursor = conn.cursor()

    for job_title, job_url in job_links:
        print(f"Processing: {job_title[:30]}...")
        
        try:
            driver.get(job_url)
            # Smart Wait: Wait until body text is present
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(1) # Small buffer for dynamic content
            
            desc_soup = BeautifulSoup(driver.page_source, "html.parser")
            
            if desc_soup.body:
                # 1. Get Clean Description
                # usage of separator=' ' ensures words don't merge (e.g. HeaderContent -> Header Content)
                raw_text = desc_soup.body.get_text(separator=' ', strip=True) 
                clean_text = clean_wellfound_text(raw_text)
                
                if len(clean_text) < 100: # Lowered threshold to avoid skipping short valid listings
                    continue

                # 2. Extract Metadata (Company, Location, Remote)
                page_title = driver.title
                company, location, is_remote = extract_meta_data(desc_soup, page_title)

                # 3. Database Insert (Updated to match Schema)
                try:
                    insert_query = """
                    INSERT INTO job_openings 
                    (search_query, job_url, job_title, raw_description, company, location_scraped, is_remote) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        "Wellfound Scraper", 
                        job_url, 
                        job_title, 
                        clean_text, 
                        company, 
                        location, 
                        is_remote
                    )
                    cursor.execute(insert_query, values)
                    conn.commit()
                    print(f"Saved: {job_title} at {company}")
                    
                except mysql.connector.Error as err:
                    if err.errno == 1062:
                        print("Skipping duplicate.")
                    else:
                        print(f"DB Error: {err}")
            else:
                print("Empty body content.")

        except Exception as e:
            print(f"Failed to process {job_url}: {e}")

    driver.quit()
    cursor.close()
    conn.close()
    print("Scraping finished.")

if __name__ == "__main__":
    scrape_wellfound()