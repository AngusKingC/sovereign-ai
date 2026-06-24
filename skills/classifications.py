"""Skill classifications — registers all built-in skills with the taxonomy.

Single responsibility: One place to declare every skill's tier,
auto-invoke conditions, and approval requirements.
"""
from core.skill_taxonomy import (
    SkillClassification,
    SkillTaxonomyRegistry,
    SkillTier,
)


def build_default_registry() -> SkillTaxonomyRegistry:
    """Build and return the default skill classification registry."""
    registry = SkillTaxonomyRegistry()

    # USER_INVOKED skills — only activated by explicit user request
    registry.register(SkillClassification(
        skill_name="calculator",
        tier=SkillTier.USER_INVOKED,
        description="Perform mathematical calculations",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="clipboard",
        tier=SkillTier.USER_INVOKED,
        description="Read from and write to the system clipboard",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="code_execution",
        tier=SkillTier.USER_INVOKED,
        description="Execute code snippets in a sandboxed environment",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="docker",
        tier=SkillTier.USER_INVOKED,
        description="Manage Docker containers and images",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="email",
        tier=SkillTier.HYBRID,
        description="Send and read email messages",
        auto_invoke_conditions=["task mentions checking email or inbox", "user asks about unread messages"],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="file_reader",
        tier=SkillTier.USER_INVOKED,
        description="Read file contents from disk",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="file_writer",
        tier=SkillTier.USER_INVOKED,
        description="Write content to files on disk",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="git",
        tier=SkillTier.USER_INVOKED,
        description="Perform Git operations on repositories",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="pdf",
        tier=SkillTier.USER_INVOKED,
        description="Read and process PDF documents",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="screenshot",
        tier=SkillTier.USER_INVOKED,
        description="Capture screenshots of the desktop or windows",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="spreadsheet",
        tier=SkillTier.USER_INVOKED,
        description="Read and write spreadsheet files",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="terminal",
        tier=SkillTier.USER_INVOKED,
        description="Execute terminal/shell commands",
        auto_invoke_conditions=[],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="transcription",
        tier=SkillTier.USER_INVOKED,
        description="Transcribe audio files to text",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="tts",
        tier=SkillTier.USER_INVOKED,
        description="Convert text to speech audio",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="web_scraper",
        tier=SkillTier.USER_INVOKED,
        description="Scrape content from web pages",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="web_search",
        tier=SkillTier.USER_INVOKED,
        description="Search the web for information",
        auto_invoke_conditions=[],
        requires_approval=False,
    ))

    # AGENT_INVOKED skills — the orchestrator decides to use automatically
    registry.register(SkillClassification(
        skill_name="marine_ais",
        tier=SkillTier.AGENT_INVOKED,
        description="Track vessel positions via AIS data",
        auto_invoke_conditions=["task mentions vessel tracking or AIS", "maritime safety check"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_weather",
        tier=SkillTier.AGENT_INVOKED,
        description="Monitor marine weather conditions",
        auto_invoke_conditions=["task mentions weather or sea conditions", "passage planning"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_tidal",
        tier=SkillTier.AGENT_INVOKED,
        description="Check tidal information and predictions",
        auto_invoke_conditions=["task mentions tides or tidal streams", "coastal navigation"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="marine_passage_planner",
        tier=SkillTier.AGENT_INVOKED,
        description="Plan maritime passages with route optimization",
        auto_invoke_conditions=["task mentions passage planning or routing", "long-distance voyage"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="calendar",
        tier=SkillTier.AGENT_INVOKED,
        description="Manage calendar events and schedules",
        auto_invoke_conditions=["task mentions scheduling or events", "user asks about availability"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="home_assistant",
        tier=SkillTier.AGENT_INVOKED,
        description="Control smart home devices via Home Assistant",
        auto_invoke_conditions=["task mentions smart home, lights, or devices", "environment control request"],
        requires_approval=True,
    ))
    registry.register(SkillClassification(
        skill_name="http_client",
        tier=SkillTier.AGENT_INVOKED,
        description="Make HTTP requests to external APIs",
        auto_invoke_conditions=["task requires external API call", "data retrieval from URL"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="notes",
        tier=SkillTier.AGENT_INVOKED,
        description="Create and manage notes",
        auto_invoke_conditions=["task mentions taking notes or remembering", "user shares information to store"],
        requires_approval=False,
    ))
    registry.register(SkillClassification(
        skill_name="reminder",
        tier=SkillTier.AGENT_INVOKED,
        description="Set and manage reminders",
        auto_invoke_conditions=["task mentions reminding or alerting", "time-based action needed"],
        requires_approval=False,
    ))

    return registry
