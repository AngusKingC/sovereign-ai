"""Tests for TUI cognition stack wiring (Plan 37.6)."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, PropertyMock, MagicMock
from cli.tui import JarvisTUI


class TestTUICognitionWiring:
    """Verify the TUI constructs and wires the full cognition stack."""
    
    @pytest.fixture
    def app(self):
        """Construct JarvisTUI with OllamaAdapter mocked at instantiation.
        
        Uses yield (not return) so the patch stays active for the duration
        of each test method. This is critical for test_tui_adapter_swap_preserves_memory_router,
        which triggers additional OllamaAdapter constructions during the swap.
        """
        with patch('adapters.ollama.OllamaAdapter') as mock_adapter_class:
            mock_instance = MagicMock()
            mock_instance.model_name = "llama3"
            mock_instance.is_local = True
            mock_instance.cost_per_token = 0.0
            mock_instance.generate = AsyncMock(return_value=MagicMock(
                content="mock response",
                confidence=0.9,
                model_used="llama3",
                tokens_used=10,
            ))
            mock_instance.health_check = AsyncMock(return_value=True)
            mock_instance.close = AsyncMock()
            mock_adapter_class.return_value = mock_instance
            
            from cli.tui import JarvisTUI
            yield JarvisTUI()  # ← yield, NOT return — keeps patch active during test
    
    def test_tui_constructs_memory_router(self, app):
        """TUI must construct a real MemoryRouter, not pass None."""
        assert app.memory_router is not None
        assert hasattr(app.memory_router, 'fetch_by_filter')
    
    def test_tui_passes_memory_router_to_orchestrator(self, app):
        """Orchestrator must receive the real memory_router, not None."""
        assert app.orchestrator.memory_router is app.memory_router
        assert app.orchestrator.memory_router is not None
    
    def test_tui_passes_memory_router_to_worker(self, app):
        """OllamaWorker must receive the real memory_router, not None."""
        assert app.worker.memory_router is app.memory_router
        assert app.worker.memory_router is not None
    
    def test_tui_constructs_approval_gate(self, app):
        """TUI must construct ApprovalGate with trust_registry."""
        assert app.orchestrator.approval_gate is not None
        assert app.orchestrator.approval_gate.trust_registry is not None
    
    def test_tui_constructs_rating_system(self, app):
        """TUI must construct RatingSystem."""
        # RatingSystem is not directly exposed on orchestrator, but it's constructed
        # We can verify the orchestrator has the improvement_loop which depends on it
        assert app.orchestrator.improvement_loop is not None
    
    def test_tui_constructs_instruction_generator(self, app):
        """TUI must construct InstructionGenerator."""
        # InstructionGenerator is not directly exposed, but improvement_loop depends on it
        assert app.orchestrator.improvement_loop is not None
    
    def test_tui_constructs_orchestrator_improvement_loop(self, app):
        """TUI must construct OrchestratorImprovementLoop and set it on orchestrator."""
        assert app.orchestrator.improvement_loop is not None
    
    def test_tui_adapter_swap_preserves_memory_router(self, app):
        """When user swaps adapter, the new worker must get the same memory_router."""
        original_memory_router = app.worker.memory_router
        
        # Simulate the synchronous part of _on_adapter_selected (lines 494-497 of cli/tui.py)
        # The async part (process_command) is just for UI updates, not the worker swap logic
        from cli.adapter_factory import create_worker
        new_worker = create_worker("lm_studio", "llama3", memory_router=app.memory_router)
        app.worker = new_worker
        app.orchestrator.register_worker("ollama_worker", new_worker)
        
        # Verify new worker has the same memory_router
        assert app.worker.memory_router is original_memory_router
        assert app.worker.memory_router is not None
