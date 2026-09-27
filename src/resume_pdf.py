"""
Renders a tailored resume (output of tailor_agent.tailor_resume) plus the
fixed header/education/skills sections into an ATS-friendly single-column
PDF using reportlab.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

from src.config import load_resume

NAME_STYLE = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=15, alignment=TA_CENTER, spaceAfter=1)
CONTACT_STYLE = ParagraphStyle("Contact", fontName="Helvetica", fontSize=9, alignment=TA_CENTER, spaceAfter=7)
SECTION_STYLE = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=6, spaceAfter=3, textColor="#1a1a1a")
ROLE_STYLE = ParagraphStyle("Role", fontName="Helvetica-Bold", fontSize=9.7, spaceAfter=0)
DATE_STYLE = ParagraphStyle("Date", fontName="Helvetica-Oblique", fontSize=9, spaceAfter=2)
CONTEXT_STYLE = ParagraphStyle("Context", fontName="Helvetica-Oblique", fontSize=8.5, spaceAfter=3, textColor="#333333")
BULLET_STYLE = ParagraphStyle("Bullet", fontName="Helvetica", fontSize=9.3, leading=11.7, spaceAfter=2)
SKILLS_LABEL_STYLE = ParagraphStyle("SkillsLabel", fontName="Helvetica-Bold", fontSize=9.3, spaceAfter=1)
SKILLS_STYLE = ParagraphStyle("Skills", fontName="Helvetica", fontSize=9.3, spaceAfter=3, leading=11.7)


def _bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(item["text"], BULLET_STYLE), leftIndent=10, spaceAfter=1) for item in items],
        bulletType="bullet",
        start="\u2022",
        leftIndent=12,
    )


def render_resume_pdf(tailored: dict, output_path: str):
    resume = load_resume()
    header = resume["header"]

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    story = []

    story.append(Paragraph(header["name"], NAME_STYLE))
    contact_line = f'{header["location"]} | {header["phone"]} | {header["email"]} | {header["linkedin"]}'
    story.append(Paragraph(contact_line, CONTACT_STYLE))

    # Education
    story.append(Paragraph("EDUCATION", SECTION_STYLE))
    for edu in resume["education"]:
        story.append(Paragraph(f'{edu["school"]}<br/>{edu["degree"]}', ROLE_STYLE))
        story.append(Paragraph(edu["dates"], DATE_STYLE))

    # Skills
    story.append(Paragraph("SKILLS", SECTION_STYLE))
    for label, value in resume["skills"].items():
        story.append(Paragraph(f"<b>{label}:</b> {value}", SKILLS_STYLE))

    # Work experience
    story.append(Paragraph("WORK EXPERIENCE", SECTION_STYLE))

    vectra = next(e for e in resume["experience"] if e["id"] == "vectra")
    story.append(Paragraph(f'{vectra["company"]} \u2014 {vectra["role"]}', ROLE_STYLE))
    story.append(Paragraph(vectra["dates"], DATE_STYLE))
    if vectra.get("context"):
        story.append(Paragraph(vectra["context"], CONTEXT_STYLE))
    story.append(_bullets(tailored["vectra"]))
    story.append(Spacer(1, 3))

    meta = next(e for e in resume["experience"] if e["id"] == "meta")
    story.append(Paragraph(f'{meta["company"]} \u2014 {meta["role"]}', ROLE_STYLE))
    story.append(Paragraph(meta["dates"], DATE_STYLE))
    story.append(_bullets(tailored["meta"]))

    # Projects
    story.append(Paragraph("PROJECTS", SECTION_STYLE))
    capstone = resume["projects"][0]
    story.append(Paragraph(capstone["name"], ROLE_STYLE))
    story.append(Paragraph(capstone["dates"], DATE_STYLE))
    story.append(_bullets(tailored["capstone"]))

    # Extracurricular
    story.append(Paragraph("EXTRACURRICULAR", SECTION_STYLE))
    for line in resume["extracurricular"]:
        story.append(Paragraph(f"\u2022 {line}", BULLET_STYLE))

    doc.build(story)
    return output_path
