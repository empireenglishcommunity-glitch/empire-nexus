"""Guide deep-links: !help <topic> / !guide <topic> map to guide anchors.

Companion to the completed student guide — lets anyone be sent straight to the
exact section (e.g. /guide#streaks). Verifies the topic map only points at real
anchors and the commands are registered.
"""
from src import bot as botmod

# The anchors that actually exist in site/guide/index.html (student guide).
VALID_ANCHORS = {
    "quickstart", "access", "tasks", "server", "calendar", "streaks", "points",
    "levels", "pronunciation", "itqan", "notifications", "privacy", "install",
    "troubleshoot", "commands", "review", "glossary", "rules", "rights",
}


def test_guide_link_builds_anchor_url():
    assert botmod._guide_link("streaks").endswith("/guide#streaks")
    assert botmod._guide_link().endswith("/guide")


def test_all_topics_point_at_real_anchors():
    assert set(botmod._GUIDE_TOPICS.values()) <= VALID_ANCHORS


def test_key_topics_resolve_en_and_ar():
    assert botmod._GUIDE_TOPICS["streaks"] == "streaks"
    assert botmod._GUIDE_TOPICS["نطق"] == "pronunciation"      # Arabic
    assert botmod._GUIDE_TOPICS["اختبار"] == "itqan"
    assert botmod._GUIDE_TOPICS["دخول"] == "access"


def test_guide_and_help_commands_registered():
    assert botmod.bot.get_command("guide") is not None
    assert botmod.bot.get_command("help") is not None
