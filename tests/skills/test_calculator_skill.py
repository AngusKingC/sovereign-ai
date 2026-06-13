"""Calculator skill tests."""

import pytest

from skills.calculator.skill import CalculatorSkill
from core.observability import MemoryTraceEmitter, TraceEventType, TraceComponent


pytestmark = pytest.mark.asyncio


class TestCalculatorSkill:
    """Test CalculatorSkill functionality."""

    @pytest.fixture
    def calculator_skill(self):
        """Create a calculator skill for testing."""
        return CalculatorSkill(
            emitter=MemoryTraceEmitter(),
        )

    async def test_calculate_returns_correct_result_for_basic_arithmetic(self, calculator_skill):
        """Test calculate() returns correct result for basic arithmetic."""
        result = await calculator_skill.calculate("2 + 3 * 4")
        
        assert result["success"] is True
        assert result["result"] == 14

    async def test_calculate_handles_complex_expression(self, calculator_skill):
        """Test calculate() handles complex expression (parentheses, multiple operators)."""
        result = await calculator_skill.calculate("(2 + 3) * (4 - 1)")
        
        assert result["success"] is True
        assert result["result"] == 15

    async def test_calculate_returns_failure_dict_for_invalid_expression(self, calculator_skill):
        """Test calculate() returns failure dict for invalid expression — does not raise."""
        result = await calculator_skill.calculate("2 + * 3")
        
        assert result["success"] is False
        assert result["result"] is None
        assert "error" in result

    async def test_calculate_rejects_dangerous_expressions(self, calculator_skill):
        """Test calculate() rejects dangerous expressions (import, exec, eval) — returns failure dict."""
        result = await calculator_skill.calculate("import os")
        
        assert result["success"] is False
        assert result["result"] is None
        assert "dangerous" in result["error"].lower()

    async def test_convert_units_correctly_converts_length_units(self, calculator_skill):
        """Test convert_units() correctly converts length units."""
        result = await calculator_skill.convert_units(1000, "m", "km")
        
        assert result["success"] is True
        assert result["result"] == 1.0

    async def test_convert_units_correctly_converts_temperature(self, calculator_skill):
        """Test convert_units() correctly converts temperature (C to F and back)."""
        result_c_to_f = await calculator_skill.convert_units(0, "C", "F")
        assert result_c_to_f["success"] is True
        assert result_c_to_f["result"] == 32.0
        
        result_f_to_c = await calculator_skill.convert_units(32, "F", "C")
        assert result_f_to_c["success"] is True
        assert abs(result_f_to_c["result"] - 0.0) < 0.01

    async def test_convert_units_returns_failure_dict_for_unsupported_unit(self, calculator_skill):
        """Test convert_units() returns failure dict for unsupported unit — does not raise."""
        result = await calculator_skill.convert_units(100, "m", "lb")
        
        assert result["success"] is False
        assert result["result"] is None
        assert "error" in result

    async def test_trace_event_emitted_with_expression_in_data(self, calculator_skill):
        """Test trace event emitted with expression in data."""
        await calculator_skill.calculate("2 + 2")
        
        events = calculator_skill._emitter.get_events()
        assert len(events) > 0
        assert any(event.event_type == TraceEventType.CALCULATOR_OPERATION for event in events)
        assert any(event.component == TraceComponent.CALCULATOR_SKILL for event in events)
        assert any(event.data.get("expression") == "2 + 2" for event in events)
