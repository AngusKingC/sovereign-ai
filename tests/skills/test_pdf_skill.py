"""PDF skill tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from skills.pdf.skill import PdfSkill
from core.approval_gate import ApprovalGate, ApprovalResponse
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestPdfSkill:
    """Test PdfSkill functionality."""

    @pytest.fixture
    def pdf_skill(self):
        """Create a PDF skill for testing."""
        return PdfSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
        )

    async def test_extract_text_returns_string_content(self, pdf_skill):
        """Test extract_text() returns string content from mocked PDF."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test content"
        mock_pdf.pages.__iter__ = Mock(return_value=iter([mock_page]))
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("os.path.exists", return_value=True):
                result = await pdf_skill.extract_text("test.pdf")

        assert result == "Test content"

    async def test_extract_pages_reads_only_specified_pages(self, pdf_skill):
        """Test extract_pages() reads only specified pages."""
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "Page 1"
        mock_pdf.pages[1].extract_text.return_value = "Page 2"
        mock_pdf.pages[2].extract_text.return_value = "Page 3"
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("pdfplumber.open", return_value=mock_pdf):
            result = await pdf_skill.extract_pages("test.pdf", [1, 3])

        assert "Page 1" in result
        assert "Page 3" in result
        assert "Page 2" not in result

    async def test_page_count_returns_correct_integer(self, pdf_skill):
        """Test page_count() returns correct integer."""
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("pdfplumber.open", return_value=mock_pdf):
            result = await pdf_skill.page_count("test.pdf")

        assert result == 3

    async def test_generate_requires_approval_gate(self):
        """Test generate() requires ApprovalGate approval, returns success dict."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=True,
            approved_by="test-user",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        pdf_skill = PdfSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        with patch("reportlab.lib.pagesizes.letter"):
            with patch("reportlab.lib.styles.getSampleStyleSheet"):
                with patch("reportlab.platypus.SimpleDocTemplate"):
                    with patch("reportlab.platypus.Paragraph"):
                        result = await pdf_skill.generate("output.pdf", "content", "title")

        assert result["success"] is True
        mock_approval_gate.request_approval.assert_called_once()

    async def test_generate_denied_by_approval_gate(self):
        """Test generate() denied by approval gate — no file written."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_response = ApprovalResponse(
            request_id="test-request-id",
            task_id="test-task-id",
            approved=False,
            approved_by="test-user",
            decision_reason="Test denial",
        )
        mock_approval_gate.request_approval = AsyncMock(return_value=mock_response)

        pdf_skill = PdfSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        result = await pdf_skill.generate("output.pdf", "content", "title")

        assert result["success"] is False

    async def test_extract_text_raises_file_not_found(self, pdf_skill):
        """Test extract_text() raises FileNotFoundError for missing file."""
        with patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await pdf_skill.extract_text("missing.pdf")

    async def test_trace_event_emitted_with_correct_enum_values(self, pdf_skill):
        """Test trace event emitted with correct enum values and operation name."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test"
        mock_pdf.pages.__iter__ = Mock(return_value=iter([mock_page]))
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("os.path.exists", return_value=True):
                await pdf_skill.extract_text("test.pdf")

        events = pdf_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.PDF_OPERATION for event in events)
        assert any(event.component == TraceComponent.PDF_SKILL for event in events)
        assert any(event.data.get("operation") == "extract_text" for event in events)

    async def test_extract_text_on_encrypted_pdf_returns_empty_string(self, pdf_skill):
        """Test extract_text() on encrypted/unreadable PDF returns empty string — does not raise."""
        mock_pdf = MagicMock()
        mock_pdf.__enter__ = Mock(side_effect=Exception("Encrypted"))
        mock_pdf.__exit__ = Mock(return_value=None)

        with patch("pdfplumber.open", return_value=mock_pdf):
            with patch("os.path.exists", return_value=True):
                result = await pdf_skill.extract_text("encrypted.pdf")

        assert result == ""
