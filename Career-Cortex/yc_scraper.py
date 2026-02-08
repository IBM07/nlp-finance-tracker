"""Career Cortex - Y Combinator Startup Job Scraper"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import mysql.connector
import re

from config import settings

# Get user input for job role search
role = input("Enter The Desired Role: ")

# Configuration constants
YC_JOBS_URL = f"https://www.workatastartup.com/jobs?query={role}" 
SCROLL_PAUSE_TIME = settings.SCROLL_PAUSE_TIME
MAX_SCROLLS = 15  # YC has fewer jobs, keep lower limit


def get_db_connection():
    """Establish and return database connection"""
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset=settings.DB_CHARSET
    )


def clean_yc_text(raw_text):
    """
    Remove Y Combinator specific page noise from scraped text
    Returns cleaned text suitable for database storage
    """
    # Known YC page elements that aren't job content
    noise_patterns = [
        "Menu Work at a Startup",
        "Startup Jobs Internships Upcoming Events How it Works Log In",
        "› Work at a Startup",
        "Software Engineer jobs at Y Combinator startups",
        "Find open roles and connect with founders",
        "About What Happens at YC?",
        "Apply YC Interview Guide FAQ People YC Blog",
        "Companies Startup Directory Founder Directory Launch YC",
        "Startup Jobs All Jobs ◦ Engineering ◦ Operations ◦ Marketing ◦ Sales",
        "Internships Startup Job Guide YC Startup Jobs Blog",
        "Jobs by role:",
        "Jobs by Location",
        "Sign up to see more ›"
    ]

    cleaned_text = raw_text
    
    # Remove each noise pattern from the text
    for pattern in noise_patterns:
        cleaned_text = cleaned_text.replace(pattern, "")

    # Normalize whitespace - collapse multiple spaces/newlines into single spaces
    cleaned_text = " ".join(cleaned_text.split())
    
    return cleaned_text

def scrape_yc():
    """Main function to scrape Y Combinator job listings"""
    print(f"Starting YC scraper for: {YC_JOBS_URL}")

    # Configure Chrome browser options
    options = Options()
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    
    # Navigate to Y Combinator jobs page
    driver.get(YC_JOBS_URL)
    time.sleep(5)  # Initial page load wait

    # Infinite scroll implementation to load all job listings
    print("Scrolling to load complete job list...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    for scroll_attempt in range(MAX_SCROLLS):
        # Scroll to bottom of page
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        
        # Check if page height changed (new content loaded)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("Scroll complete - all content loaded")
            break
            
        last_height = new_height
        print(f"Scroll iteration {scroll_attempt + 1}/{MAX_SCROLLS}")

    # Parse HTML content after scrolling
    print("Extracting job links from page content...")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    job_links = []
    seen_urls = set()  # Track URLs to avoid duplicates
    
    # Target roles to include (case-insensitive)
    target_roles = ["engineer", "developer", "backend", "frontend", "full stack", "python", "ai", "machine learning", "data"]
    
    # Roles to exclude from results
    exclude_roles = ["sales", "marketing", "account executive", "recruiter", "design", "operations", "customer"]

    # Process all links on the page
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if not href:
            continue
        
        # Convert relative URLs to absolute
        if href.startswith("http"):
            full_url = href
        else:
            full_url = f"https://www.workatastartup.com{href}"
        
        # Filter for job links (contain '/jobs/' and have numbers)
        if "/jobs/" not in full_url or not re.search(r"\d", full_url):
            continue
            
        # Remove query parameters and deduplicate
        full_url = full_url.split('?')[0]
        if full_url in seen_urls:
            continue
        
        # Extract job title text
        title = link.get_text(strip=True)
        if not title:
            continue
        
        # Apply role-based filtering
        title_lower = title.lower()
        if any(excluded in title_lower for excluded in exclude_roles):
            continue
        if not any(target in title_lower for target in target_roles):
            continue

        # Valid job found - add to processing list
        seen_urls.add(full_url)
        job_links.append((title, full_url))

    print(f"Found {len(job_links)} valid job listings")

    # Database operations
    conn = get_db_connection()
    cursor = conn.cursor()

    # Process each job listing
    for job_title, job_url in job_links:
        print(f"Processing: {job_title[:40]}...")
        
        try:
            # Navigate to individual job page
            driver.get(job_url)
            time.sleep(3)  # Wait for job page to load
            
            # Parse job description page
            desc_soup = BeautifulSoup(driver.page_source, "html.parser")
            
            if desc_soup.body:
                # Extract raw text content
                raw_text = desc_soup.body.get_text(separator=' ', strip=True)
                
                # Clean text to remove YC-specific noise
                clean_text = clean_yc_text(raw_text)
                
                # Skip if content is too short after cleaning
                if len(clean_text) < 200:
                    print("Insufficient content after cleaning - skipping")
                    continue

                # Insert job data into database
                try:
                    insert_query = """
                    INSERT INTO job_openings 
                    (search_query, job_url, job_title, raw_description) 
                    VALUES (%s, %s, %s, %s)
                    """
                    values = ("YC Scraper", job_url, job_title, clean_text)
                    cursor.execute(insert_query, values)
                    conn.commit()
                    print("Successfully saved to database")
                except mysql.connector.Error as db_error:
                    if db_error.errno == 1062:  # Duplicate entry error
                        print("Duplicate entry - skipping")
                    else:
                        print(f"Database error: {db_error}")
            else:
                print("No page content found")

        except Exception as error:
            print(f"Error processing {job_url}: {error}")

    # Cleanup resources
    driver.quit()
    cursor.close()
    conn.close()
    print("YC scraping completed")

if __name__ == "__main__":
    scrape_yc()
