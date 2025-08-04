import streamlit as st
from fpdf import FPDF
import docx2txt
from pdfminer.high_level import extract_text as extract_pdf_text
import re
import requests
from bs4 import BeautifulSoup

# ----------------------- Resume Helpers -------------------------
def extract_text_from_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        return extract_pdf_text(uploaded_file)
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return docx2txt.process(uploaded_file)
    else:
        return "Unsupported file type."

def score_resume(text, jd_text=""):
    base_keywords = [
        "python", "java", "sql", "aws", "html", "css", "javascript",
        "machine learning", "data analysis", "c++", "react", "docker",
        "tensorflow", "pandas", "numpy"
    ]
    jd_keywords = re.findall(r'\b\w+\b', jd_text.lower())
    combined_keywords = list(set(base_keywords + jd_keywords))
    found = [kw for kw in combined_keywords if kw in text.lower()]
    missing = list(set(combined_keywords) - set(found))

    score = min(100, len(found) * 5)
    feedback = []

    if not re.search(r'\b\d{10}\b', text):
        feedback.append("⚠️ Add a valid 10-digit phone number.")
    if not re.search(r'\S+@\S+', text):
        feedback.append("⚠️ Add a professional email address.")
    if "project" not in text.lower():
        feedback.append("🔧 Highlight projects to show practical skills.")
    if "experience" not in text.lower():
        feedback.append("💼 Include internships or job experiences.")
    if len(text.split()) < 150:
        feedback.append("📄 Add more content. Your resume seems too short.")

    return score, found, missing[:10], feedback

def generate_pdf(data):
    file_name = f"{data['name'].replace(' ', '_')}_Resume.pdf"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, txt=data['name'], ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=data['email'], ln=True)
    pdf.cell(200, 10, txt=data['phone'], ln=True)
    pdf.ln(5)

    for section in ["summary", "skills", "education", "experience", "projects", "certifications"]:
        if data[section].strip():
            pdf.set_font("Arial", "B", 12)
            pdf.cell(200, 10, txt=section.capitalize(), ln=True)
            pdf.set_font("Arial", size=10)
            pdf.multi_cell(0, 8, data[section])
            pdf.ln(3)

    pdf.output(file_name)
    return file_name

def scrape_linkedin_profile(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        name_tag = soup.find("title")
        name = name_tag.text.split(" |")[0] if name_tag else "LinkedIn User"
        return {
            "name": name,
            "email": "user@example.com",
            "phone": "1234567890",
            "summary": f"{name} - Skilled professional from LinkedIn.",
            "skills": "LinkedIn, Profile, Analysis",
            "education": "Bachelor's Degree from LinkedIn University",
            "experience": "Experience at LinkedIn",
            "projects": "Project: LinkedIn Automation",
            "certifications": "Certified LinkedIn Learner"
        }
    except Exception as e:
        return None

# ----------------------- Session State -------------------------
if 'page' not in st.session_state:
    st.session_state.page = "home"
def goto(p): st.session_state.page = p

# ----------------------- Styling -------------------------
st.set_page_config(page_title="Resumind", layout="wide")
st.markdown("""
<style>
.card {
    background: #fdfdfd;
    border: 2px solid #f3f3f3;
    border-radius: 14px;
    padding: 1.5rem;
    text-align: center;
    transition: 0.2s;
}
.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 6px 15px rgba(0,0,0,0.1);
}
.icon { font-size: 2rem; }
.upload-box {
    border: 2px dashed #b2c7ff;
    background: #f4f7ff;
    border-radius: 14px;
    padding: 2rem;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ----------------------- Pages -------------------------
def home():
    st.markdown("## 🎓 Welcome to Resumind!")
    st.markdown("Craft, Upload, Analyze or Import your resume in one place.")
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    if col1.button("✍️ Create New Resume"): goto("create")
    col1.markdown("<div class='card'><div class='icon'>✍️</div><h4>Create Resume</h4><p>Start from scratch with AI help</p></div>", unsafe_allow_html=True)

    if col2.button("🔗 Import from LinkedIn"): goto("linkedin")
    col2.markdown("<div class='card'><div class='icon'>🔗</div><h4>Import from LinkedIn</h4><p>Paste your LinkedIn URL and generate resume</p></div>", unsafe_allow_html=True)

    if col3.button("📄 Upload Existing Resume"): goto("upload")
    col3.markdown("<div class='card'><div class='icon'>📄</div><h4>Upload Resume</h4><p>Edit existing resume files</p></div>", unsafe_allow_html=True)

    if col4.button("📊 Check Resume Score"): goto("score")
    col4.markdown("<div class='card'><div class='icon'>📊</div><h4>Check Score</h4><p>ATS score and keyword insights</p></div>", unsafe_allow_html=True)

def create_resume():
    st.header("✍️ Create Resume")
    with st.form("resume_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        summary = st.text_area("Summary / Objective")
        skills = st.text_area("Skills (comma-separated)")
        education = st.text_area("Education")
        experience = st.text_area("Experience")
        projects = st.text_area("Projects")
        certifications = st.text_area("Certifications")
        submitted = st.form_submit_button("Generate PDF Resume")

    if submitted:
        data = {
            "name": name, "email": email, "phone": phone, "summary": summary,
            "skills": skills, "education": education, "experience": experience,
            "projects": projects, "certifications": certifications
        }
        filename = generate_pdf(data)
        with open(filename, "rb") as f:
            st.download_button("📥 Download Resume", f, file_name=filename)

    if st.button("⬅️ Back"): goto("home")

def import_linkedin():
    st.header("🔗 Import from LinkedIn")
    url = st.text_input("Paste your LinkedIn profile URL")
    if st.button("Generate Resume"):
        profile_data = scrape_linkedin_profile(url)
        if profile_data:
            st.success(f"✅ Resume generated for {profile_data['name']}")
            filename = generate_pdf(profile_data)
            with open(filename, "rb") as f:
                st.download_button("📥 Download Resume PDF", f, file_name=filename)
        else:
            st.error("❌ Could not extract profile info. Try a public LinkedIn profile.")

    if st.button("⬅️ Back"): goto("home")

def upload_resume():
    st.header("📄 Upload and Edit Resume")
    file = st.file_uploader("Upload your resume (PDF/DOCX)")
    if file:
        text = extract_text_from_file(file)
        st.text_area("Resume Content", value=text, height=400)
    if st.button("⬅️ Back"): goto("home")

def score_page():
    st.header("📊 Resume Score Checker")
    st.markdown("<div class='upload-box'><b>📤 Upload Resume</b><br>Max 200MB • PDF/DOCX</div>", unsafe_allow_html=True)
    file = st.file_uploader("Upload Resume", type=["pdf", "docx"])
    jd_text = st.text_area("📌 Paste Job Description (optional)", help="Used to suggest relevant keywords")

    if file:
        text = extract_text_from_file(file)
        score, found, missing, feedback = score_resume(text, jd_text)

        st.success(f"✅ ATS Score: {score}/100")
        st.progress(score)

        if found:
            st.write("✅ **Found Keywords:**")
            st.write(", ".join(found))
        if missing:
            st.warning("💡 **Suggested Keywords to Add:**")
            st.write(", ".join(missing))
        if feedback:
            st.write("📝 **Feedback:**")
            for item in feedback:
                st.info(item)

    if st.button("⬅️ Back"): goto("home")

# ----------------------- Page Router -------------------------
page = st.session_state.page
if page == "home": home()
elif page == "create": create_resume()
elif page == "linkedin": import_linkedin()
elif page == "upload": upload_resume()
elif page == "score": score_page()
