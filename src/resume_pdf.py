"""
Renders a tailored resume (output of tailor_agent.tailor_resume) plus the
fixed header/education/skills sections into an ATS-friendly single-column
PDF using reportlab.

Every experience and project entry in the resume file is rendered, in file
order, so the layout follows whatever is in resume_bullets.seed.json.
"""
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

from src.agents.tailor_agent import default_sections
from src.config import load_resume

NAME_STYLE = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=15, alignment=TA_CENTER, spaceAfter=1)
CONTACT_STYLE = ParagraphStyle("Contact", fontName="Helvetica", fontSize=9, alignment=TA_CENTER, spaceAfter=7)
SECTION_STYLE = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=6, spaceAfter=3, textColor="#1a1a1a")
ROLE_STYLE = ParagraphStyle("Role", fontName="Helvetica-Bold", fontSize=9.7, spaceAfter=0)
DATE_STYLE = ParagraphStyle("Date", fontName="Helvetica-Oblique", fontSize=9, spaceAfter=2)
CONTEXT_STYLE = ParagraphStyle("Context", fontName="Helvetica-Oblique", fontSize=8.5, spaceAfter=3, textColor="#333333")
BULLET_STYLE = ParagraphStyle("Bullet", fontName="Helvetica", fontSize=9.3, leading=11.7, spaceAfter=2)
SKILLS_STYLE = ParagraphStyle("Skills", fontName="Helvetica", fontSize=9.3, spaceAfter=3, leading=11.7)


def _p(text, style):
    """Paragraph with user text escaped, so characters like & or < cannot break the PDF."""
    return Paragraph(escape(text), style)


def _bullets(items):
    return ListFlowable(
        [ListItem(_p(item["text"], BULLET_STYLE), leftIndent=10, spaceAfter=1) for item in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
    )


def render_resume_pdf(tailored: dict, output_path: str) -> int:
    """Write the PDF and return its page count (a one-page resume returns 1).

    `tailored` is the output of tailor_resume(); pass {} to render the
    untailored resume. Any section missing from it uses its default bullets.
    """
    resume = load_resume()
    header = resume["header"]
    chosen = (tailored or {}).get("sections", {})
    defaults = default_sections(resume)

    def bullets_for(section):
        return _bullets(chosen.get(section["id"]) or defaults[section["id"]])

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    story = []

    story.append(_p(header["name"], NAME_STYLE))
    contact_line = f'{header["location"]} | {header["phone"]} | {header["email"]} | {header["linkedin"]}'
    story.append(_p(contact_line, CONTACT_STYLE))

    # Education
    story.append(Paragraph("EDUCATION", SECTION_STYLE))
    for edu in resume["education"]:
        story.append(Paragraph(f'{escape(edu["school"])}<br/>{escape(edu["degree"])}', ROLE_STYLE))
        story.append(_p(edu["dates"], DATE_STYLE))

    # Skills
    story.append(Paragraph("SKILLS", SECTION_STYLE))
    for label, value in resume["skills"].items():
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(value)}", SKILLS_STYLE))

    # Work experience
    story.append(Paragraph("WORK EXPERIENCE", SECTION_STYLE))
    jobs = resume.get("experience", [])
    for i, job in enumerate(jobs):
        story.append(_p(f'{job["company"]} — {job["role"]}', ROLE_STYLE))
        story.append(_p(job["dates"], DATE_STYLE))
        if job.get("context"):
            story.append(_p(job["context"], CONTEXT_STYLE))
        story.append(bullets_for(job))
        if i < len(jobs) - 1:
            story.append(Spacer(1, 3))

    # Projects
    projects = resume.get("projects", [])
    if projects:
        story.append(Paragraph("PROJECTS", SECTION_STYLE))
        for i, project in enumerate(projects):
            story.append(_p(project["name"], ROLE_STYLE))
            story.append(_p(project["dates"], DATE_STYLE))
            story.append(bullets_for(project))
            if i < len(projects) - 1:
                story.append(Spacer(1, 3))

    # Extracurricular
    if resume.get("extracurricular"):
        story.append(Paragraph("EXTRACURRICULAR", SECTION_STYLE))
        for line in resume["extracurricular"]:
            story.append(_p(f"• {line}", BULLET_STYLE))

    doc.build(story)
    return doc.page
