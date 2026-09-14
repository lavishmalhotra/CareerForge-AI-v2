from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from groq import Groq
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity
import os
import json
import sqlite3
import re
from datetime import datetime

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-this")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

DB_NAME = "careerforge.db"

CAREER_SKILLS = {
    "data analyst": "python sql excel data visualization tableau power bi statistics pandas numpy",
    "machine learning engineer": "python machine learning deep learning tensorflow pytorch scikit-learn statistics numpy pandas",
    "business intelligence developer": "sql power bi tableau data warehousing etl python reporting dashboards",
    "software engineer": "python java data structures algorithms git system design apis",
    "data scientist": "python statistics machine learning pandas numpy sql visualization deep learning",
    "web developer": "html css javascript react node flask django git apis",
    "backend developer": "python java sql apis databases system design flask django node",
    "ai engineer": "python machine learning deep learning nlp tensorflow pytorch llm apis",
    "devops engineer": "docker kubernetes ci cd linux aws cloud automation git",
    "product manager": "communication analytics roadmapping agile stakeholder management sql",
}


# ---------- Database setup ----------

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tool_type TEXT,
            input_summary TEXT,
            result_json TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def save_to_history(user_id, tool_type, input_summary, result_data):
    conn = get_db()
    conn.execute(
        "INSERT INTO history (user_id, tool_type, input_summary, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, tool_type, input_summary, json.dumps(result_data),
         datetime.now().strftime("%d %b %Y, %I:%M %p"))
    )
    conn.commit()
    conn.close()


def get_history(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM history WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    conn.close()
    history = []
    for row in rows:
        history.append({
            "id": row["id"],
            "tool_type": row["tool_type"],
            "input_summary": row["input_summary"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"]
        })
    return history


# ---------- Auth (Flask-Login) ----------

class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["name"], row["email"])
    return None


# ---------- Helper functions ----------

def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text)
    text = re.sub(r"```$", "", text)
    return json.loads(text.strip())


def compute_skill_gap(user_skills_text, career_title):
    key = career_title.lower().strip()
    required = CAREER_SKILLS.get(key, "python sql communication problem solving analytics")

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform([user_skills_text.lower(), required])
    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]

    user_words = set(re.findall(r"[a-zA-Z+#]+", user_skills_text.lower()))
    required_words = set(required.split())
    missing = sorted(required_words - user_words)

    return {"score": round(float(similarity) * 100, 1), "missing_skills": missing[:6]}


JD_EXTRA_STOPWORDS = {
    'experience', 'strong', 'required', 'requirement', 'requirements', 'ability', 'candidate',
    'candidates', 'looking', 'work', 'working', 'years', 'year', 'skills', 'skill', 'knowledge',
    'understanding', 'plus', 'preferred', 'responsibilities', 'role', 'team', 'environment',
    'including', 'etc', 'using', 'proficient', 'proficiency', 'familiarity', 'familiar', 'join',
    'good', 'excellent', 'minimum', 'degree', 'related', 'field', 'company', 'apply', 'tools',
    'like', 'll', 've'
}
JD_STOPWORDS = list(ENGLISH_STOP_WORDS.union(JD_EXTRA_STOPWORDS))


def extract_keywords(jd_text, top_n=15):
    vectorizer = CountVectorizer(stop_words=JD_STOPWORDS, ngram_range=(1, 1), max_features=top_n)
    matrix = vectorizer.fit_transform([jd_text.lower()])
    freqs = matrix.toarray()[0]
    vocab = vectorizer.get_feature_names_out()
    order = freqs.argsort()[::-1]
    return [vocab[i] for i in order if freqs[i] > 0]


def compute_ats_score(resume_text, job_description):
    resume_lower = resume_text.lower()

    keywords = extract_keywords(job_description) if job_description.strip() else []
    matched = [k for k in keywords if k in resume_lower]
    missing_keywords = [k for k in keywords if k not in matched]
    keyword_score = (len(matched) / len(keywords) * 100) if keywords else 0

    sections = ['experience', 'education', 'skills', 'project']
    sections_found = [s for s in sections if s in resume_lower]
    section_score = (len(sections_found) / len(sections)) * 100

    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resume_text))
    has_phone = bool(re.search(r'(\+?\d{1,3}[-.\s]?)?\d{10}', resume_text))
    contact_score = ((has_email + has_phone) / 2) * 100

    if keywords:
        overall = round((keyword_score * 0.5) + (section_score * 0.3) + (contact_score * 0.2), 1)
    else:
        overall = round((section_score * 0.6) + (contact_score * 0.4), 1)

    tips = []
    if keywords and missing_keywords:
        tips.append(f"Add these keywords if relevant: {', '.join(missing_keywords[:8])}.")
    if not keywords:
        tips.append("Paste a job description above for a keyword-match score.")
    missing_sections = [s for s in sections if s not in sections_found]
    if missing_sections:
        tips.append(f"Add clear section headers for: {', '.join(missing_sections)}.")
    if not has_email:
        tips.append("Add a professional email address.")
    if not has_phone:
        tips.append("Add a phone number.")

    return {
        "overall_score": overall,
        "keyword_score": round(keyword_score, 1),
        "section_score": round(section_score, 1),
        "contact_score": round(contact_score, 1),
        "matched_keywords": matched,
        "tips": tips
    }


def read_pdf(file_storage):
    reader = PdfReader(file_storage)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def call_llm(prompt):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# ---------- Public routes ----------

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with this email already exists.")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        user_row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        user = User(user_row["id"], user_row["name"], user_row["email"])
        login_user(user)
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        user_row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user_row and check_password_hash(user_row["password_hash"], password):
            user = User(user_row["id"], user_row["name"], user_row["email"])
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


# ---------- Dashboard ----------

@app.route("/dashboard")
@login_required
def dashboard():
    history = get_history(current_user.id)
    return render_template("dashboard.html", history_count=len(history))


# ---------- Tool 1: Career Path Suggester ----------

@app.route("/career-path", methods=["GET", "POST"])
@login_required
def career_path():
    if request.method == "GET":
        return render_template("career_path.html")

    name = request.form.get("name")
    education = request.form.get("education")
    skills = request.form.get("skills")
    interests = request.form.get("interests")
    resume_file = request.files.get("resume")

    resume_text = ""
    if resume_file and resume_file.filename != "":
        resume_text = read_pdf(resume_file)

    if resume_text:
        profile_info = f"Resume content:\n{resume_text}"
        skills_for_ml = resume_text
    else:
        profile_info = f"Name: {name}\nEducation: {education}\nSkills: {skills}\nInterests: {interests}"
        skills_for_ml = skills or ""

    prompt = f"""
    You are a career guidance expert. Based on this profile, suggest 3 career paths.

    {profile_info}

    If the information above is missing, too vague, or appears to be random/test text, respond with this exact JSON:
    {{"valid": false, "message": "Please provide valid details about your education, skills, and interests so I can suggest suitable career paths."}}

    Otherwise, respond ONLY with valid JSON in this exact format, nothing else before or after:
    {{
      "valid": true,
      "careers": [
        {{"title": "Career Name", "reason": "Why it fits, 2 lines.", "match": 85}},
        {{"title": "Career Name", "reason": "Why it fits, 2 lines.", "match": 78}},
        {{"title": "Career Name", "reason": "Why it fits, 2 lines.", "match": 72}}
      ]
    }}
    """

    result_data = extract_json(call_llm(prompt))

    if result_data.get("valid") and result_data.get("careers"):
        top = result_data["careers"][0]
        gap = compute_skill_gap(skills_for_ml, top["title"])
        result_data["careers"][0]["ml_score"] = gap["score"]
        result_data["careers"][0]["missing_skills"] = gap["missing_skills"]

    save_to_history(current_user.id, "Career Path", name or "Resume upload", result_data)
    return render_template("career_path_results.html", data=result_data)


# ---------- Tool 2: ATS Resume Score Checker ----------

@app.route("/ats-score", methods=["GET", "POST"])
@login_required
def ats_score():
    if request.method == "GET":
        return render_template("ats_score.html")

    resume_file = request.files.get("resume")
    job_description = request.form.get("job_description", "")

    if not resume_file or resume_file.filename == "":
        flash("Please upload a resume PDF.")
        return redirect(url_for("ats_score"))

    resume_text = read_pdf(resume_file)
    result = compute_ats_score(resume_text, job_description)

    save_to_history(current_user.id, "ATS Score", "Resume check", result)
    return render_template("ats_results.html", data=result)


# ---------- Tool 3: Interview Question Generator ----------

@app.route("/interview-prep", methods=["GET", "POST"])
@login_required
def interview_prep():
    if request.method == "GET":
        return render_template("interview_prep.html")

    role = request.form.get("role")

    prompt = f"""
    Generate 5 realistic interview questions for the role: {role}.
    For each question, also give a short model answer (2-3 lines).

    Respond ONLY with valid JSON in this exact format:
    {{
      "role": "{role}",
      "questions": [
        {{"question": "...", "answer": "..."}},
        {{"question": "...", "answer": "..."}},
        {{"question": "...", "answer": "..."}},
        {{"question": "...", "answer": "..."}},
        {{"question": "...", "answer": "..."}}
      ]
    }}
    """

    result_data = extract_json(call_llm(prompt))
    save_to_history(current_user.id, "Interview Prep", role, result_data)
    return render_template("interview_results.html", data=result_data)


# ---------- Tool 4: Cover Letter Generator ----------

@app.route("/cover-letter", methods=["GET", "POST"])
@login_required
def cover_letter():
    if request.method == "GET":
        return render_template("cover_letter.html")

    name = request.form.get("name")
    role = request.form.get("role")
    company = request.form.get("company")
    highlights = request.form.get("highlights")

    prompt = f"""
    Write a professional, concise cover letter (under 250 words) for:
    Name: {name}
    Applying for: {role}
    Company: {company}
    Key highlights to mention: {highlights}

    Return only the cover letter text, no extra commentary.
    """

    letter_text = call_llm(prompt)
    save_to_history(current_user.id, "Cover Letter", f"{role} at {company}", {"letter": letter_text})
    return render_template("cover_letter_result.html", letter=letter_text, role=role, company=company)


# ---------- History ----------

@app.route("/history")
@login_required
def history():
    records = get_history(current_user.id)
    return render_template("history.html", records=records)


init_db()

if __name__ == "__main__":
    app.run(debug=True)