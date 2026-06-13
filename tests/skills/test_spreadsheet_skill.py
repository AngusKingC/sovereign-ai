"""Spreadsheet skill tests."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from skills.spreadsheet.skill import SpreadsheetSkill
from core.approval_gate import ApprovalGate
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestSpreadsheetSkill:
    """Test SpreadsheetSkill functionality."""

    @pytest.fixture
    def spreadsheet_skill(self):
        """Create a spreadsheet skill for testing."""
        return SpreadsheetSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=None,
        )

    async def test_read_csv_returns_correctly_parsed_list_of_dicts(self, spreadsheet_skill):
        """Test read_csv() returns correctly parsed list of dicts."""
        mock_csv = MagicMock()
        mock_csv.__enter__ = Mock(return_value=mock_csv)
        mock_csv.__exit__ = Mock(return_value=None)
        
        mock_reader = MagicMock()
        mock_reader.__iter__ = Mock(return_value=iter([
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]))
        
        with patch("builtins.open", return_value=mock_csv):
            with patch("csv.DictReader", return_value=mock_reader):
                with patch("os.path.exists", return_value=True):
                    result = await spreadsheet_skill.read_csv("test.csv")

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == "25"

    async def test_write_csv_requires_approval_returns_correct_row_count(self):
        """Test write_csv() requires approval, returns correct row count."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        spreadsheet_skill = SpreadsheetSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        mock_csv = MagicMock()
        mock_csv.__enter__ = Mock(return_value=mock_csv)
        mock_csv.__exit__ = Mock(return_value=None)

        with patch("builtins.open", return_value=mock_csv):
            with patch("csv.DictWriter") as mock_writer:
                result = await spreadsheet_skill.write_csv("test.csv", [{"name": "Alice"}])

        assert result["success"] is True
        assert result["rows_written"] == 1
        mock_approval_gate.request_approval.assert_called_once()

    async def test_write_csv_denied_by_approval_gate(self):
        """Test write_csv() denied by approval gate — no file written."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=False)

        spreadsheet_skill = SpreadsheetSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        result = await spreadsheet_skill.write_csv("test.csv", [{"name": "Alice"}])

        assert result["success"] is False
        assert result["rows_written"] == 0

    async def test_read_excel_returns_correctly_parsed_list_of_dicts(self, spreadsheet_skill):
        """Test read_excel() returns correctly parsed list of dicts."""
        mock_wb = MagicMock()
        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            ("name", "age"),
            ("Alice", 30),
            ("Bob", 25),
        ]
        mock_wb.active = mock_ws
        mock_wb.__enter__ = Mock(return_value=mock_wb)
        mock_wb.__exit__ = Mock(return_value=None)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            with patch("os.path.exists", return_value=True):
                result = await spreadsheet_skill.read_excel("test.xlsx")

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["age"] == 25

    async def test_write_excel_requires_approval_returns_correct_row_count(self):
        """Test write_excel() requires approval, returns correct row count."""
        mock_approval_gate = Mock(spec=ApprovalGate)
        mock_approval_gate.request_approval = AsyncMock(return_value=True)

        spreadsheet_skill = SpreadsheetSkill(
            emitter=MemoryTraceEmitter(),
            approval_gate=mock_approval_gate,
        )

        mock_wb = MagicMock()
        mock_ws = MagicMock()
        mock_wb.active = mock_ws
        mock_wb.__enter__ = Mock(return_value=mock_wb)
        mock_wb.__exit__ = Mock(return_value=None)

        with patch("openpyxl.Workbook", return_value=mock_wb):
            result = await spreadsheet_skill.write_excel("test.xlsx", [{"name": "Alice"}])

        assert result["success"] is True
        assert result["rows_written"] == 1
        mock_approval_gate.request_approval.assert_called_once()

    async def test_sheet_names_returns_list_of_strings(self, spreadsheet_skill):
        """Test sheet_names() returns list of strings."""
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1", "Sheet2", "Data"]
        mock_wb.__enter__ = Mock(return_value=mock_wb)
        mock_wb.__exit__ = Mock(return_value=None)

        with patch("openpyxl.load_workbook", return_value=mock_wb):
            with patch("os.path.exists", return_value=True):
                result = await spreadsheet_skill.sheet_names("test.xlsx")

        assert len(result) == 3
        assert "Sheet1" in result
        assert "Data" in result

    async def test_trace_event_emitted_with_correct_enum_values(self, spreadsheet_skill):
        """Test trace event emitted with correct enum values."""
        mock_csv = MagicMock()
        mock_csv.__enter__ = Mock(return_value=mock_csv)
        mock_csv.__exit__ = Mock(return_value=None)
        
        mock_reader = MagicMock()
        mock_reader.__iter__ = Mock(return_value=iter([{"name": "Alice"}]))
        
        with patch("builtins.open", return_value=mock_csv):
            with patch("csv.DictReader", return_value=mock_reader):
                with patch("os.path.exists", return_value=True):
                    await spreadsheet_skill.read_csv("test.csv")

        events = spreadsheet_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.SPREADSHEET_OPERATION for event in events)
        assert any(event.component == TraceComponent.SPREADSHEET_SKILL for event in events)

    async def test_read_csv_on_missing_file_raises_file_not_found(self, spreadsheet_skill):
        """Test read_csv() on missing file raises FileNotFoundError — not swallowed."""
        with patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await spreadsheet_skill.read_csv("missing.csv")
