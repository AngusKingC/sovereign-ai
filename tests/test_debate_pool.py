"""
Tests for DebatePool (memory/debate_pool.py).

Tests cover pool creation, solution/critique/score storage, retrieval,
and cleanup. No LLM calls — pure data structure operations.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from memory.debate_pool import (
    DebatePool,
    DebateTask,
    ExpertCritique,
    ExpertSolution,
    JudgeScore,
)


@pytest.fixture
def temp_pool_root():
    """Temporary directory for debate pool tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_task():
    """Sample debate task for testing."""
    return DebateTask(
        task_id="test_task_1",
        prompt="Write a game with 60fps rendering",
        task_type="game",
    )


@pytest.fixture
def sample_solution():
    """Sample expert solution for testing."""
    return ExpertSolution(
        expert_id="expert_A",
        expert_name="Expert A",
        round_number=1,
        solution_code="def render(): pass",
    )


@pytest.fixture
def sample_critique():
    """Sample expert critique for testing."""
    return ExpertCritique(
        expert_id="expert_B",
        expert_name="Expert B",
        round_number=1,
        target_expert_id="expert_A",
        critique_text="The render function is incomplete.",
    )


def test_create_pool_creates_directory_structure(temp_pool_root, sample_task):
    """Verify pool dir + subdirs created."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool_dir = pool.create_pool(sample_task)

    assert pool_dir.exists()
    assert (pool_dir / "task.json").exists()
    assert (pool_dir / "context").exists()
    assert (pool_dir / "context").is_dir()


def test_save_solution_writes_file(temp_pool_root, sample_task, sample_solution):
    """Verify solution file written with correct content."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    solution_file = pool.save_solution(sample_task.task_id, sample_solution)

    assert solution_file.exists()
    content = solution_file.read_text(encoding="utf-8")
    assert "def render(): pass" in content
    assert "expert_A_solution.py" in solution_file.name


def test_save_critique_writes_file(temp_pool_root, sample_task, sample_critique):
    """Verify critique file written."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    critique_file = pool.save_critique(sample_task.task_id, sample_critique)

    assert critique_file.exists()
    content = critique_file.read_text(encoding="utf-8")
    assert "The render function is incomplete." in content
    assert "expert_B_critique_expert_A.md" in critique_file.name


def test_save_scores_writes_json(temp_pool_root, sample_task):
    """Verify scores JSON written."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    scores = [
        JudgeScore(
            round_number=1,
            expert_id="expert_A",
            scores={"mypy": 10.0, "pytest": 8.5},
            quality_pct=92.5,
            feedback="Good work",
        )
    ]
    scores_file = pool.save_scores(sample_task.task_id, scores)

    assert scores_file.exists()
    data = json.loads(scores_file.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["expert_id"] == "expert_A"
    assert data[0]["quality_pct"] == 92.5


def test_save_scores_raises_on_empty_list(temp_pool_root, sample_task):
    """Verify ValueError on empty scores list."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)

    with pytest.raises(ValueError, match="Cannot save empty scores list"):
        pool.save_scores(sample_task.task_id, [])


def test_get_solutions_returns_all_for_round(
    temp_pool_root, sample_task, sample_solution
):
    """Verify retrieval."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    pool.save_solution(sample_task.task_id, sample_solution)

    solutions = pool.get_solutions(sample_task.task_id, 1)
    assert len(solutions) == 1
    assert solutions[0].expert_id == "expert_A"
    assert solutions[0].solution_code == "def render(): pass"


def test_get_critiques_returns_all_for_round(
    temp_pool_root, sample_task, sample_critique
):
    """Verify retrieval."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    pool.save_critique(sample_task.task_id, sample_critique)

    critiques = pool.get_critiques(sample_task.task_id, 1)
    assert len(critiques) == 1
    assert critiques[0].expert_id == "expert_B"
    assert critiques[0].target_expert_id == "expert_A"


def test_get_debate_history_concatenates_rounds(
    temp_pool_root, sample_task, sample_solution, sample_critique
):
    """Verify history string."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool.create_pool(sample_task)
    pool.save_solution(sample_task.task_id, sample_solution)
    pool.save_critique(sample_task.task_id, sample_critique)

    history = pool.get_debate_history(sample_task.task_id)
    assert "## Round 1" in history
    assert "### expert_A solution:" in history
    assert "def render(): pass" in history
    assert "### Critique:" in history
    assert "The render function is incomplete." in history


def test_cleanup_pool_removes_directory(temp_pool_root, sample_task):
    """Verify cleanup."""
    pool = DebatePool(pool_root=temp_pool_root)
    pool_dir = pool.create_pool(sample_task)

    assert pool_dir.exists()
    pool.cleanup_pool(sample_task.task_id)
    assert not pool_dir.exists()


def test_pool_root_created_if_not_exists():
    """Verify auto-creation of pool root."""
    temp_dir = tempfile.mkdtemp()
    pool_root = f"{temp_dir}/nonexistent/subdir"
    try:
        DebatePool(pool_root=pool_root)
        assert Path(pool_root).exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_rsplit_fix_handles_expert_ids_with_underscores(temp_pool_root):
    """Rev2 fix: rsplit handles expert IDs with underscores (e.g., 'expert_solution_A')."""
    pool = DebatePool(pool_root=temp_pool_root)
    task = DebateTask(task_id="test_underscore", prompt="Test", task_type="script")
    pool.create_pool(task)

    # Expert ID with "solution" in name would corrupt with old replace() logic
    solution = ExpertSolution(
        expert_id="expert_solution_A",
        expert_name="Expert Solution A",
        round_number=1,
        solution_code="def test(): pass",
    )
    pool.save_solution(task.task_id, solution)

    solutions = pool.get_solutions(task.task_id, 1)
    assert len(solutions) == 1
    assert solutions[0].expert_id == "expert_solution_A"  # Not corrupted to "expert__A"
