"""Calculator skill for mathematical operations and unit conversions."""

import asyncio
import ast
import math
import operator
from typing import Any

from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class CalculatorSkill:
    """Calculator skill for mathematical operations and unit conversions."""

    # Safe operators for expression evaluation
    _SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Safe functions for expression evaluation
    _SAFE_FUNCTIONS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }

    # Unit conversion factors (to base units)
    _UNIT_CONVERSIONS = {
        # Length: base = meters
        "mm": 0.001,
        "cm": 0.01,
        "m": 1.0,
        "km": 1000.0,
        "in": 0.0254,
        "ft": 0.3048,
        "mi": 1609.344,
        # Weight: base = kilograms
        "g": 0.001,
        "kg": 1.0,
        "lb": 0.453592,
        "oz": 0.0283495,
        # Temperature: special handling
        "C": "celsius",
        "F": "fahrenheit",
        "K": "kelvin",
    }

    _UNIT_CATEGORIES = {
        "length": ["mm", "cm", "m", "km", "in", "ft", "mi"],
        "weight": ["g", "kg", "lb", "oz"],
        "temperature": ["C", "F", "K"],
    }

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
    ) -> None:
        """Initialize the calculator skill.

        Args:
            emitter: Trace emitter for observability
        """
        self._emitter = emitter or MemoryTraceEmitter()

    async def calculate(self, expression: str) -> dict[str, Any]:
        """Evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            Dict with result, expression, and success. On invalid expression returns failure dict with error.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator calculate",
                data={"expression": expression},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        # Check for dangerous expressions
        dangerous_keywords = ["import", "exec", "eval", "__", "open", "file"]
        if any(keyword in expression.lower() for keyword in dangerous_keywords):
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            return {
                "result": None,
                "expression": expression,
                "success": False,
                "error": "Dangerous expression rejected",
            }

        try:
            result = self._safe_eval(expression)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator calculate completed",
                data={"expression": expression, "success": success},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        return {
            "result": result,
            "expression": expression,
            "success": success,
            "error": error,
        }

    def _safe_eval(self, expression: str) -> float | int:
        """Safely evaluate a mathematical expression using AST.

        Args:
            expression: Expression to evaluate

        Returns:
            Evaluated result

        Raises:
            ValueError: If expression is invalid
        """
        try:
            node = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid syntax: {e}")

        return self._eval_node(node.body)

    def _eval_node(self, node: ast.AST) -> float | int:
        """Recursively evaluate an AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Evaluated result

        Raises:
            ValueError: If node type is not allowed
        """
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type in self._SAFE_OPERATORS:
                return self._SAFE_OPERATORS[op_type](left, right)
            else:
                raise ValueError(f"Operator not allowed: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)
            if op_type in self._SAFE_OPERATORS:
                return self._SAFE_OPERATORS[op_type](operand)
            else:
                raise ValueError(f"Operator not allowed: {op_type}")
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            if func_name in self._SAFE_FUNCTIONS:
                args = [self._eval_node(arg) for arg in node.args]
                return self._SAFE_FUNCTIONS[func_name](*args)
            else:
                raise ValueError(f"Function not allowed: {func_name}")
        elif isinstance(node, ast.Name):
            if node.id in self._SAFE_FUNCTIONS:
                return self._SAFE_FUNCTIONS[node.id]
            else:
                raise ValueError(f"Name not allowed: {node.id}")
        else:
            raise ValueError(f"Node type not allowed: {type(node)}")

    async def convert_units(self, value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
        """Convert between common units.

        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Dict with result, from, to, and success. Returns failure dict for unsupported conversions.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator convert_units",
                data={"from": from_unit, "to": to_unit, "value": value},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        # Check if units are supported
        if from_unit not in self._UNIT_CONVERSIONS or to_unit not in self._UNIT_CONVERSIONS:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            return {
                "result": None,
                "from": from_unit,
                "to": to_unit,
                "success": False,
                "error": "Unsupported unit",
            }

        # Check if units are in the same category
        from_category = None
        to_category = None
        for category, units in self._UNIT_CATEGORIES.items():
            if from_unit in units:
                from_category = category
            if to_unit in units:
                to_category = category

        if from_category != to_category:
            duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            return {
                "result": None,
                "from": from_unit,
                "to": to_unit,
                "success": False,
                "error": "Cannot convert between different unit categories",
            }

        # Temperature conversion (special handling)
        if from_category == "temperature":
            result = self._convert_temperature(value, from_unit, to_unit)
        else:
            # Linear conversion using base unit
            from_factor = self._UNIT_CONVERSIONS[from_unit]
            to_factor = self._UNIT_CONVERSIONS[to_unit]
            base_value = value * from_factor
            result = base_value / to_factor

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator convert_units completed",
                data={"from": from_unit, "to": to_unit, "result": result},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        return {
            "result": result,
            "from": from_unit,
            "to": to_unit,
            "success": True,
        }

    def _convert_temperature(self, value: float, from_unit: str, to_unit: str) -> float:
        """Convert temperature between Celsius, Fahrenheit, and Kelvin.

        Args:
            value: Temperature value
            from_unit: Source unit (C, F, K)
            to_unit: Target unit (C, F, K)

        Returns:
            Converted temperature
        """
        # Convert to Celsius first
        if from_unit == "C":
            celsius = value
        elif from_unit == "F":
            celsius = (value - 32) * 5 / 9
        elif from_unit == "K":
            celsius = value - 273.15
        else:
            raise ValueError(f"Unknown temperature unit: {from_unit}")

        # Convert from Celsius to target
        if to_unit == "C":
            return celsius
        elif to_unit == "F":
            return celsius * 9 / 5 + 32
        elif to_unit == "K":
            return celsius + 273.15
        else:
            raise ValueError(f"Unknown temperature unit: {to_unit}")

    async def supported_conversions(self) -> dict[str, Any]:
        """Return dict of supported unit categories and their units.

        Returns:
            Dict of unit categories and their units
        """
        start_time = asyncio.get_event_loop().time()

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator supported_conversions",
                data={},
                duration_ms=0,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

        try:
            event = TraceEvent(
                event_type=TraceEventType.CALCULATOR_OPERATION,
                component=TraceComponent.CALCULATOR_SKILL,
                level=TraceLevel.INFO,
                message="Calculator supported_conversions completed",
                data={},
                duration_ms=duration_ms,
            )
            await self._emitter.emit(event)
        except Exception:
            pass

        return self._UNIT_CATEGORIES.copy()
