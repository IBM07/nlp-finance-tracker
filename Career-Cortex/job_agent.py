"""Career Cortex - Remote.com Job Scraper"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import mysql.connector
import urllib.parse
import time

from config import settings

class RemoteJobScraper:
    def __init__(self):
        self.db = self._init_database()
        self.driver = None
        
    def _init_database(self):
        """Initialize database connection with error handling"""
        try:
            db = mysql.connector.connect(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                autocommit=False
            )
            print("✓ Database connection established")
            return db
        except mysql.connector.Error as err:
            print(f"✗ Database connection failed: {err}")
            raise

    def _get_search_filters(self):
        """Collect and validate user search preferences"""
        filters = {}
        
        filters['search_term'] = input("Job title (Enter to skip): ").strip()
        filters['country'] = input("Country code (e.g., USA, IND): ").strip().upper()
        
        filter_options = {
            'employment_types': ["full_time", "part_time", "contractor"],
            'locations': ["remote", "hybrid", "on_site"],
            'seniorities': ["entry_level", "mid_level", "senior", "manager", "director", "executive"]
        }
        
        for key, options in filter_options.items():
            print(f"\n{key.replace('_', ' ').title()} (comma-separated):")
            print(f"Options: {', '.join(options)}")
            user_input = input("> ").strip().lower()
            if user_input:
                filters[key] = [item.strip() for item in user_input.split(',') if item.strip() in options]
        
        return filters

    def _build_search_url(self, filters):
        """Construct the search URL with query parameters"""
        base_url = "https://remote.com/jobs/all"
        params = {}
        
        if filters.get('search_term'):
            params['query'] = filters['search_term']
        if filters.get('country'):
            params['country'] = filters['country']
        if filters.get('employment_types'):
            params['employmentType'] = filters['employment_types']
        if filters.get('locations'):
            params['workplaceLocation'] = filters['locations']
        if filters.get('seniorities'):
            params['seniority'] = filters['seniorities']
        
        query_string = urllib.parse.urlencode(params, doseq=True)
        return f"{base_url}?{query_string}"

    def _setup_browser(self):
        """Configure and initialize Chrome driver"""
        options = Options()
        options.add_argument("--window-size=1920,1080")
        if settings.CHROME_HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

    def _handle_cookies(self):
        """Accept cookies if banner appears"""
        try:
            cookie_btn = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept all')]"))
            )
            cookie_btn.click()
            time.sleep(1)
        except Exception:
            pass  # No cookie banner found

    def _extract_job_links(self):
        """Extract unique job posting links from search results"""
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/jobs/']"))
        )
        
        potential_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href^='/jobs/']")
        valid_links = []
        seen_urls = set()
        
        for link in potential_links:
            try:
                href = link.get_attribute("href")
                title = link.text.strip()
                
                # Filter criteria for valid job links
                if (href and href not in seen_urls and 
                    href.count('/') >= 5 and 
                    "jobs/all" not in href and 
                    title):
                    
                    seen_urls.add(href)
                    valid_links.append((title, href))
                    
            except Exception:
                continue
                
        return valid_links

    def _scrape_job_details(self, job_title, job_url):
        """Extract and save job details from individual posting pages"""
        self.driver.get(job_url)
        time.sleep(2)  # Brief pause for content load
        
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        if not soup.body:
            return False
            
        job_description = soup.body.get_text(separator=' ', strip=True)
        
        # Clean common noise from text
        noise_phrases = [
            "Your choice regarding cookies on this site",
            "We use cookies to personalize content"
        ]
        for phrase in noise_phrases:
            job_description = job_description.replace(phrase, "")
        
        return job_description.strip()

    def _save_job_to_db(self, search_term, job_url, job_title, description):
        """Save job posting to database with duplicate prevention"""
        try:
            cursor = self.db.cursor()
            # Fixed: Removed search_query column and corrected is_extracted value
            query = """
                INSERT INTO job_openings 
                (job_title, raw_description, job_url, is_extracted) 
                VALUES (%s, %s, %s, %s)
            """
            values = (job_title, description, job_url, False)  # FALSE for boolean column
            cursor.execute(query, values)
            self.db.commit()
            cursor.close()
            return True
        except mysql.connector.Error as err:
            if err.errno == 1062:  # Duplicate entry
                return False
            else:
                print(f"Database error: {err}")
                self.db.rollback()
                return False

    def run(self):
        """Main execution method"""
        try:
            # Get user preferences
            filters = self._get_search_filters()
            search_url = self._build_search_url(filters)
            print(f"\n🔍 Searching: {search_url}")
            
            # Setup and navigate
            self._setup_browser()
            self.driver.get(search_url)
            self._handle_cookies()
            
            # Extract job listings
            job_links = self._extract_job_links()
            print(f"📊 Found {len(job_links)} job postings")
            
            # Process each job
            successful_saves = 0
            for title, url in job_links:
                print(f"Processing: {title[:60]}...")
                
                description = self._scrape_job_details(title, url)
                if description:
                    if self._save_job_to_db(filters.get('search_term', ''), url, title, description):
                        successful_saves += 1
                        print("✓ Saved")
                    else:
                        print("○ Duplicate")
                else:
                    print("✗ Failed to extract details")
            
            # Results summary
            print(f"\n🎯 Successfully saved {successful_saves}/{len(job_links)} jobs")
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
        finally:
            if self.driver:
                self.driver.quit()
            if self.db:
                self.db.close()
            print("✅ Scraping session completed")

def main():
    """Application entry point"""
    scraper = RemoteJobScraper()
    scraper.run()

if __name__ == "__main__":
    main()
