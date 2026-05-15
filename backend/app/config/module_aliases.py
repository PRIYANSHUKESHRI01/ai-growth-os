"""
Display name aliases for the three pipeline modules.
These are UI-only labels — no backend logic depends on these values.
"""

MODULE_DISPLAY_NAMES: dict[str, str] = {
    "lead_discovery": "Automation 1 — Lead Discovery",
    "lead_scoring": "Automation 2 — Lead Scoring",
    "outreach_engine": "Automation 3 — Outreach Engine",
}

PIPELINE_STEPS = [
    {"key": "lead_discovery", "label": "Lead Discovery", "step": 1},
    {"key": "lead_scoring", "label": "Lead Scoring", "step": 2},
    {"key": "outreach_engine", "label": "Outreach Engine", "step": 3},
]
