"""PDF skill for PDF reading and generation operations."""

import asyncio
from typing import Any
from datetime import datetime, timedelta
from uuid import uuid4

from core.approval_gate import ApprovalGate, ApprovalRequest, ApprovalActionType
from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class PdfSkill:
    """PDF skill for PDF reading and generation operations."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        """Initialize the PDF skill.

        Args:
            emitter: Trace emitter for observability
            approval_gate: Approval gate for write operations
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._approval_gate = approval_gate

    async def extract_text(self, path: str) -> str:
        """Extract all text from a PDF file.

        Args:
            path: Path to the PDF file

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file does not exist
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF extract_text",
                data={"operation": "extract_text", "path": path},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Check if file exists - raise FileNotFoundError outside try-except
        import os
        if not os.path.exists(path):
            raise FileNotFoundError(f"PDF file not found: {path}")

        # Import pdfplumber here to avoid import errors if not installed
        import pdfplumber

        try:
            with pdfplumber.open(path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except Exception:
            # Return empty string for encrypted/unreadable PDFs
            text = ""

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF extract_text completed",
                data={"operation": "extract_text", "path": path},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return text

    async def extract_pages(self, path: str, pages: list[int]) -> str:
        """Extract text from specified page numbers (1-indexed).

        Args:
            path: Path to the PDF file
            pages: List of page numbers (1-indexed)

        Returns:
            Extracted text content from specified pages
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF extract_pages",
                data={"operation": "extract_pages", "path": path, "pages": pages},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        import pdfplumber

        text = ""
        try:
            with pdfplumber.open(path) as pdf:
                for page_num in pages:
                    # Convert to 0-indexed
                    if page_num < 1 or page_num > len(pdf.pages):
                        continue
                    page = pdf.pages[page_num - 1]
                    text += page.extract_text() or ""
        except Exception:
            # Return empty string for encrypted/unreadable PDFs
            text = ""

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF extract_pages completed",
                data={"operation": "extract_pages", "path": path},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return text

    async def page_count(self, path: str) -> int:
        """Return number of pages in a PDF file.

        Args:
            path: Path to the PDF file

        Returns:
            Number of pages
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF page_count",
                data={"operation": "page_count", "path": path},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        import pdfplumber

        try:
            with pdfplumber.open(path) as pdf:
                count = len(pdf.pages)
        except Exception:
            count = 0

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF page_count completed",
                data={"operation": "page_count", "path": path, "count": count},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return count

    async def generate(self, output_path: str, content: str, title: str = "") -> dict[str, Any]:
        """Generate a PDF from plain text content.

        Args:
            output_path: Path where the PDF will be saved
            content: Plain text content
            title: Optional title for the PDF

        Returns:
            Dict with success and path
        """
        if self._approval_gate:
            request = ApprovalRequest(
                request_id=str(uuid4()),
                task_id=str(uuid4()),
                session_id="default",
                action_type=ApprovalActionType.FILE_WRITE,
                action_description="pdf generate",
                action_parameters={"output_path": output_path},
                risk_level="low",
                reason_for_approval="PDF generate requires approval per policy",
                expires_at=datetime.utcnow() + timedelta(seconds=300),
            )
            response = await self._approval_gate.request_approval(request)
            approved = response.approved
            if not approved:
                return {
                    "success": False,
                    "path": output_path,
                }

        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF generate",
                data={"operation": "generate", "output_path": output_path},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        # Try reportlab first, fall back to fpdf2
        success = False
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            if title:
                title_style = styles["Heading1"]
                story.append(Paragraph(title, title_style))
            
            body_style = styles["Normal"]
            # Split content into paragraphs
            for paragraph in content.split("\n\n"):
                if paragraph.strip():
                    story.append(Paragraph(paragraph, body_style))
            
            doc.build(story)
            success = True
        except ImportError:
            # Fall back to fpdf2
            try:
                from fpdf import FPDF
                
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                
                if title:
                    pdf.set_font("Arial", size=16, style="B")
                    pdf.cell(0, 10, title, ln=True)
                    pdf.set_font("Arial", size=12)
                
                # Split content into lines
                for line in content.split("\n"):
                    pdf.multi_cell(0, 10, line)
                
                pdf.output(output_path)
                success = True
            except ImportError:
                # Neither library available
                pass

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.PDF_OPERATION,
                component=TraceComponent.PDF_SKILL,
                level=TraceLevel.INFO,
                message="PDF generate completed",
                data={"operation": "generate", "output_path": output_path, "success": success},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            # Trace emission failure - non-critical, continue
            pass

        return {
            "success": success,
            "path": output_path,
        }
