"""Career Cortex - AI-Powered Resume Parser"""

import ollama
import json
import PyPDF2

from config import settings

# --- SKILL EXTRACTION PROMPT ---
SKILL_EXTRACTION_PROMPT = """
You are an expert resume analyzer. Extract ALL technical skills from the resume text provided.

EXTRACTION RULES:
1. Focus on technical skills: programming languages, frameworks, tools, platforms, databases, cloud services, methodologies
2. Normalize skill names (e.g., "React.js" → "React", "Amazon Web Services" → "AWS")
3. Include both hard skills and technologies
4. Exclude soft skills (communication, leadership, etc.)
5. Return only unique skills

OUTPUT FORMAT (JSON only, no explanations):
{
    "skills": ["skill1", "skill2", "skill3"]
}

EXAMPLES OF VALID SKILLS:
- Languages: Python, Java, JavaScript, TypeScript, C++, Go, Rust
- Frameworks: React, Django, Flask, FastAPI, Node.js, Spring Boot
- Databases: PostgreSQL, MySQL, MongoDB, Redis, Cassandra
- Cloud: AWS, GCP, Azure, EC2, Lambda, S3, Kubernetes
- Tools: Docker, Git, Jenkins, Terraform, Ansible
- Concepts: REST APIs, GraphQL, Microservices, CI/CD, Machine Learning

Return ONLY the JSON object with the skills array.
"""

def extract_text_from_pdf(pdf_file):
    """
    Extract text content from uploaded PDF file
    
    Args:
        pdf_file: File object from Streamlit file_uploader
        
    Returns:
        str: Extracted text content or empty string on failure
    """
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def extract_skills_with_ollama(resume_text: str, model: str = None) -> list:
    """
    Use Ollama LLM to extract skills from resume text
    
    Args:
        resume_text: Full text content of the resume
        model: Ollama model to use (defaults to settings.OLLAMA_MODEL)
        
    Returns:
        List of extracted skills or empty list on failure
    """
    if model is None:
        model = settings.OLLAMA_MODEL
        
    if not resume_text or len(resume_text.strip()) < 50:
        return []
    
    try:
        # Test Ollama connection
        ollama.list()
        
        # Call Ollama with the extraction prompt
        response = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': SKILL_EXTRACTION_PROMPT},
                {'role': 'user', 'content': resume_text}
            ],
            options={'temperature': 0.0},
            format='json'
        )
        
        # Parse the JSON response
        json_response = response['message']['content']
        data = json.loads(json_response)
        
        # Extract and clean skills list
        skills = data.get('skills', [])
        
        # Remove duplicates and clean whitespace
        unique_skills = []
        seen = set()
        for skill in skills:
            skill_clean = skill.strip()
            skill_lower = skill_clean.lower()
            if skill_lower and skill_lower not in seen:
                seen.add(skill_lower)
                unique_skills.append(skill_clean)
        
        return unique_skills
        
    except Exception as e:
        print(f"Ollama extraction error: {e}")
        return []

def extract_skills_fallback(resume_text):
    """
    Fallback method using keyword matching if Ollama fails
    
    Args:
        resume_text (str): Full text content of the resume
        
    Returns:
        list: List of matched skills
    """
    common_tech = [
        # Core Languages
        "python", "java", "c++", "go", "golang", "rust", "javascript", "typescript", 
        "node.js", "c#", "ruby", "php", "swift", "kotlin", "scala",
        
        # Data Structures & Algorithms
        "data structures", "algorithms", "big o", "dynamic programming",
        
        # Backend Frameworks
        "django", "flask", "fastapi", "spring boot", "express.js", "nest.js",
        
        # Frontend
        "react", "vue", "angular", "svelte", "next.js", "nuxt.js",
        
        # API Standards
        "rest api", "graphql", "grpc", "websockets",
        
        # Databases
        "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb", 
        "elasticsearch", "neo4j", "sqlite",
        
        # Cloud Platforms
        "aws", "gcp", "azure", "ec2", "lambda", "s3", "kubernetes", "docker",
        
        # DevOps & Tools
        "git", "jenkins", "gitlab ci", "github actions", "terraform", "ansible",
        
        # Testing
        "pytest", "jest", "selenium", "cypress", "postman",
        
        # AI/ML
        "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
        "nlp", "computer vision", "langchain", "huggingface",
        
        # Data Engineering
        "kafka", "airflow", "spark", "hadoop", "etl",
        
        # Others
        "linux", "bash", "agile", "scrum", "oauth", "jwt", "microservices"
    ]
    
    resume_lower = resume_text.lower()
    found_skills = []
    
    for skill in common_tech:
        if skill in resume_lower:
            # Capitalize first letter of each word
            found_skills.append(skill.title())
    
    # Remove duplicates while preserving order
    unique_skills = []
    seen = set()
    for skill in found_skills:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            unique_skills.append(skill)
    
    return unique_skills

def parse_resume(pdf_file, use_ollama: bool = True, ollama_model: str = None):
    """
    Main function to parse resume and extract skills
    
    Args:
        pdf_file: File object from Streamlit file_uploader
        use_ollama: Whether to attempt Ollama extraction
        ollama_model: Ollama model to use (defaults to settings.OLLAMA_MODEL)
        
    Returns:
        tuple: (success: bool, skills: list, message: str)
    """
    if ollama_model is None:
        ollama_model = settings.OLLAMA_MODEL
    # Extract text from PDF
    resume_text = extract_text_from_pdf(pdf_file)
    
    if not resume_text:
        return False, [], "Failed to extract text from PDF"
    
    if len(resume_text) < 100:
        return False, [], "Resume text too short - please upload a complete resume"
    
    skills = []
    
    # Try Ollama first if enabled
    if use_ollama:
        skills = extract_skills_with_ollama(resume_text, ollama_model)
        
        if skills:
            return True, skills, f"✅ Extracted {len(skills)} skills using AI"
        else:
            # Fallback to keyword matching
            skills = extract_skills_fallback(resume_text)
            if skills:
                return True, skills, f"⚠️ Ollama unavailable - extracted {len(skills)} skills using fallback method"
            else:
                return False, [], "❌ Ollama unavailable and no skills found in fallback"
    else:
        # Direct fallback mode
        skills = extract_skills_fallback(resume_text)
        if skills:
            return True, skills, f"Extracted {len(skills)} skills"
        else:
            return False, [], "No technical skills found in resume"