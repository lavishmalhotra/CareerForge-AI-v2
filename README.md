# CareerForge-AI-v2

> **An AI-powered career assistant that helps students and job seekers prepare, evaluate, and improve their careers — all in one place.**

CareerForge AI is a full-stack web application designed to make the job preparation process smarter and more personalized. It uses AI to analyze resumes, evaluate ATS compatibility, suggest career paths, generate cover letters, and help users prepare for interviews.

---

## ✨ Features

### 📄 ATS Resume Score
Upload your resume and get an AI-powered ATS evaluation.

- ATS compatibility analysis
- Resume scoring
- Improvement suggestions
- Identification of missing skills/keywords

### 🎯 Career Path Recommendation
Get personalized career-path suggestions based on your skills and interests.

- Skill-based recommendations
- Career role suggestions
- Personalized career insights

### ✉️ AI Cover Letter Generator
Generate a customized cover letter for a specific job role and company.

- Role-specific content
- Company-specific personalization
- Highlights relevant skills and experience

### 🎤 AI Interview Preparation
Prepare for interviews with AI-generated questions and guidance.

- Role-based interview preparation
- Technical and behavioral questions
- Personalized preparation material

### 📊 Career Dashboard
A centralized dashboard to access all career tools from one place.

### 🕒 History
Keep track of previously generated results and career activities.

### 🔐 User Authentication
Secure user registration and login system.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| 🐍 Python | Backend programming |
| 🌶️ Flask | Web framework |
| 🤖 Groq API | AI-powered features |
| 🗄️ SQLite | Database |
| 🌐 HTML5 | Frontend structure |
| 🎨 CSS3 | UI styling |
| 🔧 Jinja2 | Dynamic HTML templates |

---

## 🏗️ Project Structure

```text
CareerForge-AI/
│
├── static/
│   └── css/
│       └── style.css
│
├── templates/
│   ├── ats_results.html
│   ├── ats_score.html
│   ├── career_path.html
│   ├── career_path_results.html
│   ├── cover_letter.html
│   ├── cover_letter_result.html
│   ├── dashboard.html
│   ├── history.html
│   ├── index.html
│   ├── input.html
│   ├── interview_prep.html
│   ├── interview_results.html
│   ├── login.html
│   ├── results.html
│   └── signup.html
│
├── app.py
├── .gitignore
└── README.md