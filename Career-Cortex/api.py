"""
Career Cortex - REST API Backend

Provides job search, matching, and statistics endpoints.
"""

from flask import Flask, request, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
import mysql.connector
import json
import math
import re
from difflib import SequenceMatcher
from datetime import datetime, timedelta, date
import hashlib
import functools
import urllib.parse

from config import settings, get_db_connection

app = Flask(__name__)
CORS(app)

# Configuration from centralized settings
DEFAULT_PAGE_SIZE = settings.DEFAULT_PAGE_SIZE
MAX_PAGE_SIZE = settings.MAX_PAGE_SIZE
CACHE_DURATION = settings.CACHE_DURATION

# Simple in-memory cache
cache_store = {}


class CustomJSONProvider(DefaultJSONProvider):
    """Custom JSON provider that handles datetime serialization."""
    
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


app.json_provider_class = CustomJSONProvider
app.json = CustomJSONProvider(app)

def generate_cache_key(endpoint, filters):
    key_data = f"{endpoint}:{json.dumps(filters, sort_keys=True, default=str)}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cache_response(timeout=CACHE_DURATION):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            filters = dict(request.args)
            cache_key = generate_cache_key(request.endpoint, filters)
            
            if cache_key in cache_store:
                cache_data, timestamp = cache_store[cache_key]
                if datetime.now() - timestamp < timedelta(seconds=timeout):
                    return jsonify(cache_data)
            
            result = func(*args, **kwargs)
            if hasattr(result, 'status_code') and result.status_code == 200:
                cache_store[cache_key] = (result.get_json(), datetime.now())
            return result
        return wrapper
    return decorator

def clear_cache_for_endpoint(endpoint):
    keys_to_remove = [key for key in cache_store.keys() if key.startswith(endpoint)]
    for key in keys_to_remove:
        del cache_store[key]

def calculate_match_score(job_skills, user_skills):
    if not job_skills or not user_skills:
        return 0, []
    
    job_set = set(s.lower() for s in job_skills)
    user_set = set(s.lower() for s in user_skills)
    
    if not job_set:
        return 0, []

    matches = job_set.intersection(user_set)
    score = int((len(matches) / len(job_set)) * 100)
    missing = list(job_set - user_set)
    return score, missing

def serialize_date(dt):
    if isinstance(dt, (datetime, date)):
        return dt.isoformat()
    return dt

def build_search_query(filters, include_pagination=False):
    # We fetch ALL jobs first to sort them in Python by Match Score
    base_query = "SELECT * FROM job_openings WHERE 1=1"
    
    conditions = []
    parameters = []
    
    if filters.get('search'):
        search_term = filters['search']
        conditions.append("""
            (MATCH(job_title, raw_description, company, location_scraped) 
            AGAINST (%s IN NATURAL LANGUAGE MODE) 
            OR LOWER(job_title) LIKE LOWER(%s) 
            OR LOWER(company) LIKE LOWER(%s))
        """)
        parameters.extend([search_term, f"%{search_term}%", f"%{search_term}%"])
    
    if filters.get('location'):
        conditions.append("LOWER(location_scraped) LIKE LOWER(%s)")
        parameters.append(f"%{filters['location']}%")
    
    if filters.get('remote_only') == 'true':
        conditions.append("is_remote = 1")
    
    if filters.get('company'):
        conditions.append("LOWER(company) LIKE LOWER(%s)")
        parameters.append(f"%{filters['company']}%")
    
    if filters.get('job_type'):
        conditions.append("job_type = %s")
        parameters.append(filters['job_type'])
    
    if conditions:
        base_query += " AND " + " AND ".join(conditions)
    
    # Only use SQL limit if we are NOT sorting by Match Score
    # But for simplicity and correctness of Match Score sorting, we fetch all first.
    return base_query, parameters

def enhance_search_results(jobs, search_term=None, user_skills=None):
    if not jobs: return []
    
    enhanced_jobs = []
    
    for job in jobs:
        relevance_score = 0
        
        # Text Relevance
        if search_term:
            search_lower = search_term.lower()
            fields = [
                (job.get('job_title', ''), 5.0),
                (job.get('company', ''), 3.0),
                (job.get('location_scraped', ''), 2.0),
            ]
            for field, weight in fields:
                if field and search_lower in field.lower():
                    relevance_score += weight * 10
        
        # Skill Match
        skill_match_score = 0
        missing_skills = []
        
        if user_skills:
            try:
                raw_skills = job.get('required_skills')
                if raw_skills:
                    if isinstance(raw_skills, str):
                        job_skills_list = json.loads(raw_skills)
                    else:
                        job_skills_list = raw_skills
                else:
                    job_skills_list = []
                
                skill_match_score, missing_skills = calculate_match_score(job_skills_list, user_skills)
            except:
                job_skills_list = []
        
        total_score = relevance_score + (skill_match_score * 2)
        
        enhanced_jobs.append({
            "id": job['id'],
            "title": job['job_title'],
            "company": job['company'],
            "location": job['location_scraped'],
            "is_remote": bool(job['is_remote']),
            "job_type": job.get('job_type', 'Not specified'),
            "match_score": f"{skill_match_score}%",
            "match_score_int": skill_match_score,
            "relevance_score": total_score,
            "skills_missing": missing_skills,
            "apply_url": job['job_url'],
            "posted_date": serialize_date(job.get('created_at')),
        })
    
    return enhanced_jobs

@app.route("/jobs", methods=["GET"])
# REMOVED @cache_response to ensure sorting always works live
def search_jobs():
    filters = {
        'skills': request.args.get('skills'),
        'location': request.args.get('location'),
        'remote_only': request.args.get('remote_only'),
        'company': request.args.get('company'),
        'job_type': request.args.get('job_type'),
        'search': request.args.get('search'),
        'sort': request.args.get('sort', 'match_desc'),
        'page': max(1, int(request.args.get('page', 1))),
        'per_page': min(int(request.args.get('per_page', DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE),
        'min_score': request.args.get('min_score', default=0, type=int)
    }
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch ALL matching jobs
    sql_query, query_params = build_search_query(filters)
    cursor.execute(sql_query, query_params)
    all_jobs = cursor.fetchall()
    conn.close()

    # 2. Score them all
    user_skill_list = [s.strip().lower() for s in filters['skills'].split(',')] if filters['skills'] else []
    enhanced_jobs = enhance_search_results(all_jobs, filters.get('search'), user_skill_list)
    
    # 3. Apply Min Score Filter
    if filters['min_score'] > 0:
        enhanced_jobs = [j for j in enhanced_jobs if j['match_score_int'] >= filters['min_score']]
        
    # 4. GLOBAL SORTING (Python Side)
    sort_option = filters['sort']
    
    if sort_option == 'match_desc':
        # Sort by Match Score (High -> Low), then Relevance
        enhanced_jobs.sort(key=lambda x: (x['match_score_int'], x['relevance_score']), reverse=True)
    elif sort_option == 'date':
        enhanced_jobs.sort(key=lambda x: x['posted_date'], reverse=True)
    elif sort_option == 'company':
        enhanced_jobs.sort(key=lambda x: x['company'].lower())
        
    # 5. Pagination
    total_count = len(enhanced_jobs)
    total_pages = math.ceil(total_count / filters['per_page']) if total_count > 0 else 1
    
    start = (filters['page'] - 1) * filters['per_page']
    end = start + filters['per_page']
    paginated_jobs = enhanced_jobs[start:end]

    # Build Links
    base_url = request.base_url
    q_params = request.args.copy()
    
    response = {
        "pagination": {
            "current_page": filters['page'],
            "per_page": filters['per_page'],
            "total_jobs": total_count,
            "total_pages": total_pages,
            "has_next": filters['page'] < total_pages,
            "has_prev": filters['page'] > 1
        },
        "jobs": paginated_jobs
    }
    
    return jsonify(response)

# --- Other endpoints remain cached for performance ---

@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    cache_store.clear()
    return jsonify({"message": "Cache cleared"})

@app.route("/filters/options", methods=["GET"])
@cache_response(timeout=1800)
def get_filter_options():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT company FROM job_openings WHERE company IS NOT NULL ORDER BY company")
    companies = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT location_scraped FROM job_openings WHERE location_scraped IS NOT NULL ORDER BY location_scraped")
    locations = [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT job_type FROM job_openings WHERE job_type IS NOT NULL ORDER BY job_type")
    types = [r[0] for r in cursor.fetchall()]
    conn.close()
    return jsonify({"companies": companies, "locations": locations, "job_types": types})

@app.route("/jobs/stats", methods=["GET"])
@cache_response(timeout=900)
def get_job_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as total FROM job_openings")
    total = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as remote FROM job_openings WHERE is_remote = 1")
    remote = cursor.fetchone()['remote']
    conn.close()
    return jsonify({"total_jobs": total, "remote_jobs": remote})

@app.route("/jobs/suggest", methods=["GET"])
def get_search_suggestions():
    return jsonify({"suggestions": []})


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring and load balancers."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
    
    # Check database connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    return jsonify(health_status)


if __name__ == "__main__":
    print(f"🚀 Starting Career Cortex API on {settings.API_HOST}:{settings.API_PORT}")
    app.run(
        debug=settings.API_DEBUG, 
        host=settings.API_HOST,
        port=settings.API_PORT
    )
