"""
Career Cortex - AI-Powered Job Data Extractor

This module processes raw job descriptions using Ollama LLM to extract
structured data including company, location, skills, and seniority.
"""

import json
import mysql.connector
import ollama

from config import settings, get_db_connection

# --- EXTRACTION PROMPT ---
EXTRACTION_PROMPT = """
You are an expert job data extraction agent. Extract ONLY these fields from job postings and return a valid JSON object. Use the exact keys and rules below.

CRITICAL LOCATION EXTRACTION RULES:
- Search for ANY location mentions: cities (New York), countries (USA), states (California), regions (Europe)
- Look for patterns like "based in", "located in", "from [location]", "must be in [location]"
- If you see "Remote", "Work from Home", "Anywhere", "Global", set location_scraped = "Remote" AND is_remote = true
- If you see "Hybrid", set location_scraped to the actual location mentioned AND is_remote = true
- If multiple locations: use "Location1 + Location2" format
- Only use "Not specified" if absolutely no location clues exist

REMOTE STATUS DETECTION:
- is_remote = true if you see: "Remote", "Work from Home", "WFH", "Anywhere", "Global", "Virtual", "Telecommute"
- is_remote = true for "Hybrid" roles (partially remote)
- is_remote = false for on-site only roles with specific office locations

EXACT OUTPUT FORMAT (minified JSON, no extra text):
{
    "company": "string",
    "location_scraped": "string", 
    "is_remote": boolean,
    "job_type": "string",
    "seniority": "string",
    "required_skills": ["array", "of", "strings"]
}

FALLBACK VALUES:
- company: "Not specified" if no company name found
- location_scraped: "Not specified" if no location clues
- is_remote: false if no remote indicators
- job_type: "Full-time" (most common default)
- seniority: Infer from title/requirements: "Entry-level" (0-2y), "Mid-level" (3-5y), "Senior" (5+y)
- required_skills: [] empty array if none found

SKILL NORMALIZATION EXAMPLES:
- "Python programming" → "Python"
- "React.js" → "React"
- "Amazon Web Services" → "AWS"
- "Google Cloud Platform" → "GCP"
- "SQL database" → "SQL"
- "Docker containers" → "Docker"
- "Figma design" → "Figma"
- "Agile methodology" → "Agile"

STRICT EXAMPLES:
Input: "Join TechCorp as Senior Python Developer working remotely from anywhere. Must know AWS, Docker."
Output: {"company":"TechCorp","location_scraped":"Remote","is_remote":true,"job_type":"Full-time","seniority":"Senior","required_skills":["AWS","Docker","Python"]}

Input: "Python Developer needed in New York office. Requires 3+ years experience with React."
Output: {"company":"Not specified","location_scraped":"New York","is_remote":false,"job_type":"Full-time","seniority":"Mid-level","required_skills":["Python","React"]}

Return only the JSON object. No explanations.
"""


def extract_data(raw_text: str) -> dict | None:
    """
    Use Ollama LLM to extract structured data from raw job text.
    
    Args:
        raw_text: Raw job description text
        
    Returns:
        Dictionary with extracted fields or None on failure
    """
    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': EXTRACTION_PROMPT},
                {'role': 'user', 'content': raw_text}
            ],
            options={'temperature': settings.OLLAMA_TEMPERATURE},
            format='json'
        )
        
        json_data_string = response['message']['content']
        return json.loads(json_data_string)

    except json.JSONDecodeError as e:
        print(f"❌ JSON PARSING FAILED: {e}")
        return None
    except Exception as e:
        print(f"❌ LLM EXTRACTION FAILED: {e}")
        return None


def update_job_in_database(cursor, db, job_id: int, structured_data: dict) -> bool:
    """
    Update job record with extracted structured data.
    
    Args:
        cursor: Database cursor
        db: Database connection
        job_id: Job ID to update
        structured_data: Extracted data dictionary
        
    Returns:
        True on success, False on failure
    """
    try:
        skills_list = structured_data.get('required_skills', [])
        skills_json = json.dumps(skills_list)
        
        # Convert Python boolean to MySQL integer
        is_remote_int = 1 if structured_data.get('is_remote', False) else 0
        
        sql = """
        UPDATE job_openings 
        SET 
            company = %s,
            location_scraped = %s,
            is_remote = %s,
            job_type = %s,
            seniority = %s,
            required_skills = %s,
            is_extracted = TRUE
        WHERE id = %s
        """
        vals = (
            structured_data.get('company', 'Not specified'),
            structured_data.get('location_scraped', 'Not specified'),
            is_remote_int,
            structured_data.get('job_type', 'Full-time'),
            structured_data.get('seniority', 'Not specified'),
            skills_json,
            job_id
        )
        
        cursor.execute(sql, vals)
        db.commit()
        return True
        
    except mysql.connector.Error as err:
        print(f"❌ DB UPDATE FAILED: {err}")
        db.rollback()
        return False


def main():
    """Main extraction process - fetch unprocessed jobs and extract data."""
    print("\n" + "=" * 50)
    print("Career Cortex - Job Data Extractor")
    print("=" * 50)
    
    # Connect to database
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        print("✅ Database connected successfully.")
    except mysql.connector.Error as err:
        print(f"❌ DATABASE ERROR: {err}")
        print("Please ensure MySQL is running and credentials are correct.")
        return
    
    # Test Ollama connection
    try:
        ollama.list()
        print(f"✅ Ollama connection successful (using {settings.OLLAMA_MODEL}).")
    except Exception as e:
        print(f"❌ OLLAMA ERROR: {e}")
        print("Please ensure Ollama is running: ollama serve")
        cursor.close()
        db.close()
        return
    
    # Find unprocessed jobs
    print("\nStarting extraction process...")
    cursor.execute("SELECT id, raw_description FROM job_openings WHERE is_extracted = FALSE;")
    jobs_to_process = cursor.fetchall()
    
    if not jobs_to_process:
        print("No new jobs to process. Exiting.")
        cursor.close()
        db.close()
        return

    print(f"Found {len(jobs_to_process)} jobs to process.\n")
    
    success_count = 0
    fail_count = 0
    
    for job in jobs_to_process:
        job_id = job["id"]
        raw_text = job['raw_description']
        
        print(f"--- Processing Job ID: {job_id} ---")
        
        # Extract structured data from LLM
        structured_data = extract_data(raw_text)
        
        if structured_data:
            print(f"   Extracted: {structured_data.get('company', 'Unknown')} - {len(structured_data.get('required_skills', []))} skills")
            
            # Update database with extracted data
            if update_job_in_database(cursor, db, job_id, structured_data):
                print(f"✅ Job ID {job_id} updated successfully.")
                success_count += 1
            else:
                fail_count += 1
        else:
            print(f"⚠️ Job ID {job_id} - extraction failed, skipping.")
            fail_count += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"Extraction Complete: {success_count} succeeded, {fail_count} failed")
    print("=" * 50)
    
    cursor.close()
    db.close()
    print("✅ Database connection closed.")


if __name__ == "__main__":
    main()

