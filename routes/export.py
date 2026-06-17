"""
Export routes — PDF generation for revision sheets.

Endpoints:
  POST /export/revision-sheet/{subject_id}
    → Generates a revision sheet using the existing agent tool
    → Renders to PDF with reportlab
    → Returns file download response
"""

import asyncio
import io
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from routes.deps import get_db, get_current_user
from agent.tools import generate_exam_revision_sheet

router = APIRouter(prefix="/export", tags=["export"])


def _render_pdf(subject_name: str, document_text: str) -> bytes:
    """Render revision sheet markdown text to PDF bytes using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.platypus import KeepTogether

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
        title=f"{subject_name} — Revision Sheet",
        author="Study Agent",
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#4f46e5"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=20,
    )
    h1_style = ParagraphStyle(
        "CustomH1",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=14,
        spaceAfter=4,
        borderPad=4,
    )
    h2_style = ParagraphStyle(
        "CustomH2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#4f46e5"),
        spaceBefore=10,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#374151"),
        spaceAfter=4,
    )
    bullet_style = ParagraphStyle(
        "CustomBullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=2,
    )

    story = []

    # Header
    story.append(Paragraph(f"{subject_name}", title_style))
    story.append(Paragraph(
        f"Revision Sheet · Generated {datetime.utcnow().strftime('%B %d, %Y')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5")))
    story.append(Spacer(1, 0.4 * cm))

    # Parse and render markdown-like content
    for line in document_text.split("\n"):
        line = line.rstrip()

        if not line:
            story.append(Spacer(1, 0.2 * cm))
            continue

        if line.startswith("# "):
            text = line[2:].strip()
            story.append(Spacer(1, 0.3 * cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
            story.append(Paragraph(_escape_html(text), h1_style))
        elif line.startswith("## "):
            text = line[3:].strip()
            story.append(Paragraph(_escape_html(text), h2_style))
        elif line.startswith("### "):
            text = line[4:].strip()
            bold_style = ParagraphStyle("Bold", parent=body_style, fontName="Helvetica-Bold")
            story.append(Paragraph(_escape_html(text), bold_style))
        elif line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            story.append(Paragraph(f"• {_escape_html(text)}", bullet_style))
        elif line.startswith("  - ") or line.startswith("  * "):
            text = line[4:].strip()
            nested = ParagraphStyle("Nested", parent=bullet_style, leftIndent=24)
            story.append(Paragraph(f"◦ {_escape_html(text)}", nested))
        elif line.startswith("**") and line.endswith("**"):
            text = line[2:-2].strip()
            bold_s = ParagraphStyle("BoldLine", parent=body_style, fontName="Helvetica-Bold")
            story.append(Paragraph(_escape_html(text), bold_s))
        else:
            # Inline bold: **text** → <b>text</b>
            import re
            converted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            story.append(Paragraph(_escape_html(converted, skip_tags=True), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def _escape_html(text: str, skip_tags: bool = False) -> str:
    """Escape HTML special chars except when skip_tags=True (preserves <b> etc)."""
    if skip_tags:
        # Only escape & and quotes, leave < > for tags already converted
        return text.replace("&", "&amp;")
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


from pydantic import BaseModel

class ExportRequest(BaseModel):
    document_text: Optional[str] = None

@router.post("/revision-sheet/{subject_id}")
async def export_revision_sheet(
    subject_id: str,
    body: ExportRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    session_id: Optional[str] = Query(None, description="Session ID for ChromaDB lookup"),
):
    """
    Generate and download a PDF revision sheet for a subject.

    - Uses the existing generate_exam_revision_sheet agent tool OR direct markdown text
    - Renders the result to PDF using reportlab
    - Returns a downloadable PDF file

    Protected route — requires authentication.
    """
    # Validate subject ownership
    try:
        subject_oid = ObjectId(subject_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid subject ID format")

    subject = await db.subjects.find_one({
        "_id": subject_oid,
        "user_id": current_user["id"],
    })
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    subject_name = subject.get("name", "Study Subject")
    
    document_text = body.document_text

    # If no document_text provided, generate it
    if not document_text:
        # If no session_id given, look for the most recent completed session for this subject
        active_session_id = session_id
        if not active_session_id:
            recent = await db.sessions.find_one(
                {
                    "user_id": current_user["id"],
                    "subject_id": subject_id,
                    "status": "completed",
                },
                sort=[("ended_at", -1)],
            )
            if recent:
                active_session_id = str(recent["_id"])

        if not active_session_id:
            raise HTTPException(
                status_code=404,
                detail="No completed session found for this subject. Please end a session first to export a revision sheet.",
            )

        # Get topics from the session
        session_doc = await db.sessions.find_one({"_id": ObjectId(active_session_id)})
        topics = session_doc.get("topics", []) if session_doc else []

        # Build an LLM instance for generation
        from agent.nodes import _get_llm
        llm = _get_llm(temperature=0.3)

        # Generate the revision sheet (CPU-bound + LLM calls — run in thread)
        try:
            result = await generate_exam_revision_sheet(
                subject_id=subject_id,
                session_id=active_session_id,
                subject_name=subject_name,
                llm=llm,
                custom_topics=topics,
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate revision sheet: {str(e)}",
            )

        document_text = result.get("document", "")
        if not document_text:
            raise HTTPException(
                status_code=500,
                detail="Revision sheet generation returned empty content.",
            )

    # Render to PDF
    try:
        pdf_bytes = await asyncio.to_thread(_render_pdf, subject_name, document_text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF rendering failed: {str(e)}",
        )

    filename = f"{subject_name.replace(' ', '_')}_revision_sheet.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
