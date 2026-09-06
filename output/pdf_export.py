# output/pdf_export.py

import os
import tempfile
from typing import Optional
from xml.sax.saxutils import escape
import plotly.io as pio
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image as RLImage
)

def save_figure_as_image(figure, path: str) -> bool:
    try:
        pio.write_image(figure, path, width=600, height=350)
        return True
    except Exception as e:
        print(f"[PDF Export Error] Failed to export chart image: {str(e)}")
        return False

def build_pdf(pipeline_result: dict, session_id: str, chat_history: Optional[list] = None) -> str:
    """
    Build the PDF report. Returns the generated file path.
    """
    os.makedirs("uploads", exist_ok=True)
    out_path = f"uploads/report_{session_id}.pdf"

    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'title',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#1A3A5C')
    )
    h2_style = ParagraphStyle(
        'h2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2C5F8A')
    )
    body_style = styles['Normal']

    story = []
    temp_image_paths = []

    # Header
    story.append(Paragraph('Datalyze AI — Analysis Report', title_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#2C5F8A')))
    story.append(Spacer(1, 0.3 * inch))

    # Dataset Description
    description = pipeline_result.get('description', 'No description available.')
    safe_description = escape(description)
    story.append(Paragraph('Dataset Overview', h2_style))
    story.append(Paragraph(safe_description, body_style))
    story.append(Spacer(1, 0.3 * inch))

    # Executive Summary
    summary_text = pipeline_result.get('summary', 'No summary available.')
    safe_summary = escape(summary_text)
    story.append(Paragraph('Executive Summary', h2_style))
    story.append(Paragraph(safe_summary, body_style))
    story.append(Spacer(1, 0.3 * inch))

    # Pipeline Diagnostics
    story.append(Paragraph("Pipeline Diagnostics", h2_style))
    summary = pipeline_result.get("pipeline_summary", {})
    total_time = summary.get('total_pipeline_time', 0.0)
    story.append(Paragraph(
        f"<b>Total Pipeline Time:</b> {total_time} seconds",
        body_style
    ))
    successful_agents = [escape(agent.replace("_", " ").title()) for agent in summary.get("successful_agents", [])]
    story.append(Paragraph(
        f"<b>Successful Agents:</b> {', '.join(successful_agents) if successful_agents else 'None'}",
        body_style
    ))
    failed_agents = [escape(agent.replace("_", " ").title()) for agent in summary.get("failed_agents", [])]
    story.append(Paragraph(
        f"<b>Failed Agents:</b> {', '.join(failed_agents) if failed_agents else 'None'}",
        body_style
    ))
    story.append(Spacer(1, 0.3 * inch))

    # Visualization Summary
    viz = pipeline_result.get("visualization_summary", {})
    if viz:
        story.append(Paragraph("Visualization Summary", h2_style))
        for key, val in viz.items():
            safe_key = escape(key.replace('_', ' ').title())
            safe_val = escape(str(val))
            story.append(Paragraph(
                f"<b>{safe_key}:</b> {safe_val}",
                body_style
            ))
        story.append(Spacer(1, 0.3 * inch))

    # Insights
    story.append(Paragraph('Key Findings', h2_style))
    story.append(Spacer(1, 0.15 * inch))
    insights = pipeline_result.get("visualized_insights") or pipeline_result.get("insights", [])
    if not insights:
        story.append(Paragraph("No insights available.", body_style))
    else:
        for i, ins in enumerate(insights):
            question = ins.get("question", "Unknown Question")
            answer = ins.get("answer", "No answer available")
            confidence = ins.get("confidence", "low").lower()
            safe_question = escape(question)
            story.append(Paragraph(f"{i + 1}. {safe_question}", styles['Heading3']))
            badge = "High confidence" if confidence == "high" else "Medium confidence" if confidence == "medium" else "Needs review"
            safe_answer = escape(answer)
            story.append(Paragraph(f"<b>Answer:</b> {safe_answer} [{badge}]", body_style))
            critic_reason = ins.get("critic_reason")
            if critic_reason:
                safe_reason = escape(critic_reason)
                story.append(Paragraph(f"<i>Critic note:</i> {safe_reason}", body_style))
            figure = ins.get('figure')
            if figure is not None:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    img_path = tmp.name
                temp_image_paths.append(img_path)
                if save_figure_as_image(figure, img_path):
                    story.append(RLImage(img_path, width=5 * inch, height=3 * inch))
                    story.append(Spacer(1, 0.2 * inch))

    # Chat History (if provided)
    if chat_history:
        story.append(Paragraph("Chat History", h2_style))
        story.append(Spacer(1, 0.15 * inch))
        for msg in chat_history:
            role = msg.get("role", "").capitalize()
            content = msg.get("content", "")
            if role and content:
                safe_role = escape(role)
                safe_content = escape(content)
                story.append(Paragraph(f"<b>{safe_role}:</b> {safe_content}", body_style))
                story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.3 * inch))

    try:
        doc.build(story)
    finally:
        for path in temp_image_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as clean_err:
                    print(f"[PDF Export Clean Error] Failed to delete temp image at {path}: {str(clean_err)}")

    return out_path