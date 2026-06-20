"""CLI command to start the Jarvis web server."""

import asyncio
from pathlib import Path

import typer
import uvicorn

from core.auth import AuthManager
from core.observability import MemoryTraceEmitter
from core.input_sanitiser import InputSanitiser
from web.server import create_app


def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),  # nosec B104 — configurable default, user can override via --host
    port: int = typer.Option(7000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
) -> None:
    """Start the Jarvis web server.
    
    This command starts the FastAPI web server with REST and WebSocket endpoints.
    The server requires authentication via a bearer token.
    """
    # Instantiate AuthManager
    auth_manager = AuthManager()
    
    # Get or create token
    token = asyncio.run(auth_manager.get_or_create_token())
    
    # Print token on first run
    print(f"Jarvis auth token: {token} — save this, it won't be shown again")
    
    # Instantiate MemoryTraceEmitter
    emitter = MemoryTraceEmitter()
    input_sanitiser = InputSanitiser(emitter=emitter)
    
    # Import all required components
    from core.orchestrator import Orchestrator
    from core.memory_router import MemoryRouter
    from core.skill_registry import SkillRegistry
    from core.approval_trust import ApprovalTrustRegistry
    from core.approval_gate import ApprovalGate
    from core.escalation import EscalationEngine
    from core.adapter_fallback import AdapterFallbackChain
    from system.worker_persistence import WorkerPersistence
    from core.worker_factory import WorkerFactory
    from core.rating_system import RatingSystem
    from core.instruction_generator import InstructionGenerator
    from core.instruction_versioning import InstructionVersionManager
    from core.evaluator import OutputEvaluator
    from core.trace_optimiser import TraceOptimiser
    from core.orchestrator_improvement import OrchestratorImprovementLoop
    from core.task_state_machine import TaskStateMachine
    from core.worker_base import LLMAdapter
    from adapters.ollama import OllamaAdapter
    from workers.ollama_worker import OllamaWorker
    
    # Create base dependencies
    memory_router = MemoryRouter(backends={}, emitter=emitter)
    skill_registry = SkillRegistry(emitter=emitter)
    approval_trust = ApprovalTrustRegistry(memory_router=memory_router, emitter=emitter)
    
    # Create TaskStateMachine for ApprovalGate
    state_machine = TaskStateMachine(memory_router=memory_router)
    
    # Create ApprovalGate
    approval_gate = ApprovalGate(
        state_machine=state_machine,
        memory_router=memory_router,
        emitter=emitter,
        trust_registry=approval_trust
    )
    
    # Create EscalationEngine
    escalation_engine = EscalationEngine(
        approval_gate=approval_gate,
        memory_router=memory_router,
        emitter=emitter
    )
    
    # Create AdapterFallbackChain with Ollama adapter
    ollama_adapter = OllamaAdapter(model_name="qwen2.5-coder:7b", emitter=emitter)
    fallback_chain = AdapterFallbackChain(
        adapters=[(ollama_adapter, "qwen2.5-coder:7b")],
        resource_manager=None,
        approval_gate=approval_gate,
        emitter=emitter
    )
    
    # Create WorkerPersistence
    worker_persistence = WorkerPersistence(
        memory_router=memory_router,
        emitter=emitter,
        obsidian_vault_path=None
    )
    
    # Create RatingSystem
    rating_system = RatingSystem(
        memory_router=memory_router,
        emitter=emitter
    )
    
    # Create InstructionGenerator with Ollama adapter
    instruction_generator = InstructionGenerator(
        adapter=ollama_adapter,
        rating_system=rating_system,
        memory_router=memory_router,
        obsidian_vault_path=None,
        emitter=emitter
    )
    
    # Create InstructionVersionManager
    instruction_versioning = InstructionVersionManager(
        instruction_generator=instruction_generator,
        rating_system=rating_system,
        approval_gate=approval_gate,
        memory_router=memory_router,
        emitter=emitter
    )
    
    # Create OutputEvaluator
    output_evaluator = OutputEvaluator(
        llm_adapter=ollama_adapter,
        memory_router=memory_router,
        evaluator_model="default",
        emitter=emitter
    )
    
    # Create TraceOptimiser
    trace_optimiser = TraceOptimiser(
        memory_router=memory_router,
        instruction_version_manager=instruction_versioning,
        emitter=emitter
    )
    
    # Create Orchestrator first (needed by WorkerFactory and OrchestratorImprovementLoop)
    orchestrator = Orchestrator(
        memory_router=memory_router,
        improvement_loop=None,  # Will set after creating it
        cloud_fallback_model="gpt-4o",
        approval_gate=approval_gate,
        escalation_engine=escalation_engine,
        fallback_chain=fallback_chain,
        a2a_router=None,
        input_sanitiser=input_sanitiser,
        output_evaluator=output_evaluator,
        emitter=emitter
    )
    
    # Create WorkerFactory (requires orchestrator)
    # Pass None for persistence to avoid asyncio.create_task in __init__ (no event loop in serve)
    worker_factory = WorkerFactory(
        skill_registry=skill_registry,
        orchestrator=orchestrator,
        memory_router=memory_router,
        emitter=emitter,
        persistence=None,  # Skip persistence loading in non-async context
        instruction_generator=instruction_generator
    )
    
    # Create OrchestratorImprovementLoop (requires orchestrator)
    improvement_loop = OrchestratorImprovementLoop(
        orchestrator=orchestrator,
        instruction_version_manager=instruction_versioning,
        memory_router=memory_router,
        emitter=emitter
    )
    
    # Set improvement_loop on orchestrator
    orchestrator.improvement_loop = improvement_loop
    
    # Wire trace optimiser (analyses trace events for instruction updates)
    orchestrator.trace_optimiser = trace_optimiser
    
    # Construct and register OllamaWorker with Orchestrator
    ollama_worker = OllamaWorker(
        adapter=ollama_adapter,
        memory_router=memory_router,
        profile=None,  # Use default profile
    )
    orchestrator.register_worker("ollama_worker", ollama_worker)
    
    # Create FastAPI app
    app = create_app(orchestrator, auth_manager, emitter)
    
    # Start server with uvicorn
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    typer.run(serve)
