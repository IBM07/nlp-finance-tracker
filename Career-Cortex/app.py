"""Career Cortex - Streamlit Frontend Application"""

import streamlit as st
import requests
import os
from resume_parser import parse_resume

from config import settings

# Cloud-ready API URL configuration
API_BASE_URL = settings.API_URL

# --- 2. Caching & API Logic ---
@st.cache_data(ttl=60)  # Cache for 1 minute to prevent spamming
def fetch_jobs_from_api(skills_query):
    try:
        # Construct endpoint using the dynamic base URL
        api_url = f"{API_BASE_URL}/jobs"
        params = {"skills": skills_query, "per_page": 50}
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# --- 3. Page Config ---
st.set_page_config(
    page_title="CareerCortex | AI Job Agent",
    page_icon="🚀",
    layout="wide"
)

# --- 4. Session State Setup ---
# This ensures the input box updates automatically when a resume is uploaded
if 'skills_input' not in st.session_state:
    st.session_state.skills_input = "python, docker, fastapi"

if 'last_upload_time' not in st.session_state:
    st.session_state.last_upload_time = None

# --- 5. The UI ---
st.title("🚀 CareerCortex")
st.markdown("### The AI Agent that reads your resume and finds your job.")

# --- FEATURE: AI-Powered Resume Uploader ---
with st.expander("📄 Upload Resume - AI will extract your skills automatically", expanded=True):
    st.markdown("""
    **How it works:**
    1. Upload your PDF resume
    2. Local AI (Ollama) analyzes the content
    3. Skills are automatically extracted and populated
    """)
    
    uploaded_file = st.file_uploader(
        "Upload PDF Resume", 
        type="pdf",
        help="Upload your resume and let AI extract your technical skills"
    )
    
    if uploaded_file:
        # Show processing status
        with st.spinner("🤖 AI is analyzing your resume..."):
            # Parse resume using Ollama
            success, extracted_skills, message = parse_resume(
                uploaded_file, 
                use_ollama=True,
                ollama_model=settings.OLLAMA_MODEL
            )
        
        if success:
            # Update the session state with extracted skills
            st.session_state.skills_input = ", ".join(extracted_skills)
            
            # Show success message with skill preview
            st.success(message)
            
            # Display extracted skills in an organized way
            with st.container():
                st.markdown("**Extracted Skills:**")
                
                # Display skills in columns for better readability
                cols = st.columns(3)
                for idx, skill in enumerate(extracted_skills):
                    with cols[idx % 3]:
                        st.markdown(f"✓ `{skill}`")
                
                st.info("💡 Skills have been automatically added below. You can edit them if needed.")
        else:
            st.error(message)
            st.info("💡 **Troubleshooting:**")
            st.markdown(f"""
            - Ensure Ollama is running: `ollama serve`
            - Check if {settings.OLLAMA_MODEL} model is installed: `ollama list`
            - If model is missing: `ollama pull {settings.OLLAMA_MODEL}`
            - The system will use keyword matching as fallback if Ollama is unavailable
            """)

# --- Main Search Input ---
# We bind the value to session_state so the resume uploader can update it
st.markdown("---")
st.markdown("### 🔍 Search Jobs")

user_skills = st.text_input(
    "Your Skills (comma-separated)",
    key="skills_input",  # This links the input to our variable
    help="Enter skills comma-separated, or upload resume above for automatic extraction",
    placeholder="e.g., Python, React, AWS, Docker"
)

col1, col2 = st.columns([3, 1])
with col1:
    search_button = st.button("🎯 Find My Perfect Match", type="primary", use_container_width=True)
with col2:
    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.skills_input = ""
        st.rerun()

if search_button:
    if not user_skills:
        st.error("⚠️ Please enter skills or upload a resume.")
    else:
        with st.spinner(f"🔍 Searching jobs at {API_BASE_URL}..."):
            data = fetch_jobs_from_api(user_skills)

        if "error" in data:
            st.error(f"❌ Connection Failed: {data['error']}")
            st.info("💡 **Troubleshooting:**")
            st.markdown("""
            - **Running Locally:** Ensure Flask API is running on port 5000
            - **Running on GCP:** Ensure API_URL environment variable is set correctly
            - **Database:** Check if MySQL is running and accessible
            """)
        else:
            # Handle Pagination Structure
            total_count = data.get('pagination', {}).get('total_jobs', 0)
            jobs = data.get('jobs', [])

            if not jobs:
                st.warning("😔 No jobs found. Try these tips:")
                st.markdown("""
                - Use broader keywords (e.g., "Python" instead of "Python Django FastAPI")
                - Try single skills one at a time
                - Check if jobs exist in the database
                """)
            else:
                st.success(f"🎯 Found {total_count} perfect matches based on your profile!")
                st.markdown(f"*Showing top results sorted by match score*")
                
                # Display Job Cards
                for idx, job in enumerate(jobs, 1):
                    with st.container(border=True):
                        # Header Row
                        col_title, col_score = st.columns([3, 1])
                        
                        with col_title:
                            st.subheader(f"{idx}. {job['title']}")
                            
                            # Company and Location Info
                            location_emoji = '🌍' if job.get('is_remote') else '🏢'
                            st.caption(f"**{job['company']}** | {job['location']} {location_emoji}")
                            
                            # Job Type Badge
                            job_type = job.get('job_type', 'Not specified')
                            st.markdown(f"*{job_type}*")
                        
                        with col_score:
                            # Match Score Display
                            match_score = job.get('match_score_int', 0)
                            
                            # Color coding for match scores
                            if match_score >= 80:
                                score_color = "🟢"
                            elif match_score >= 50:
                                score_color = "🟡"
                            else:
                                score_color = "🔴"
                            
                            st.metric(
                                "Match", 
                                f"{match_score}%",
                                help="Percentage of required skills you possess"
                            )
                            st.markdown(f"{score_color}")
                        
                        # Missing Skills Section
                        missing_skills = job.get('skills_missing', [])
                        if missing_skills:
                            with st.expander(f"⚠️ Missing Skills ({len(missing_skills)})"):
                                st.markdown("Skills to learn for this role:")
                                for skill in missing_skills[:10]:  # Show max 10
                                    st.markdown(f"- `{skill}`")
                        
                        # Action Buttons
                        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 2])
                        
                        with col_btn1:
                            apply_url = job.get('apply_url', '#')
                            st.link_button("📝 Apply Now", apply_url, use_container_width=True)
                        
                        with col_btn2:
                            # Copy job details
                            job_summary = f"{job['title']} at {job['company']} - {match_score}% match"
                            if st.button(f"📋 Copy Details", key=f"copy_{job['id']}", use_container_width=True):
                                st.toast("Copied to clipboard!", icon="✅")
                        
                        with col_btn3:
                            # Posted date
                            posted_date = job.get('posted_date', 'Unknown')
                            st.caption(f"📅 Posted: {posted_date[:10]}")

# --- Footer ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p><strong>CareerCortex</strong> - Powered by Custom Web Scraping, Flask API, Ollama AI & Streamlit</p>
    <p>Built with ❤️ for smarter job searching</p>
</div>
""", unsafe_allow_html=True)

# Sidebar with app info
with st.sidebar:
    st.title("ℹ️ About")
    st.markdown("""
    **CareerCortex** uses:
    - 🕷️ Custom web scrapers (Remote.com, Wellfound, YC)
    - 🧠 Ollama AI for resume parsing
    - 🔍 Smart skill matching algorithm
    - ⚡ Flask REST API backend
    - 💾 MySQL database
    
    **Tech Stack:**
    - Python, Selenium, BeautifulSoup
    - Flask, MySQL, Streamlit
    - Ollama (qwen2.5:14b)
    """)
    
    st.markdown("---")
    st.markdown("### 🛠️ System Status")
    
    # Quick health check
    try:
        response = requests.get(f"{API_BASE_URL}/jobs/stats", timeout=3)
        if response.status_code == 200:
            stats = response.json()
            st.success("✅ API Connected")
            st.metric("Total Jobs", stats.get('total_jobs', 0))
            st.metric("Remote Jobs", stats.get('remote_jobs', 0))
        else:
            st.error("❌ API Error")
    except:
        st.warning("⚠️ API Offline")
    
    # Check Ollama status
    try:
        import ollama
        ollama.list()
        st.success("✅ Ollama Running")
    except:
        st.warning("⚠️ Ollama Offline")