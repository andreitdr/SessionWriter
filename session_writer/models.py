from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaggedItem:
    item_id: str
    body: str


@dataclass
class SessionFormData:
    initials: str
    sequence: str
    start: str
    charter_description: str
    selected_areas: list[str]
    versions: list[str]
    environments: list[str]
    testers: list[str]
    duration: str
    multiplier: str
    setup_pct: str
    test_pct: str
    bug_pct: str
    charter_pct: str
    opportunity_pct: str
    datafiles: list[str]
    notes: str
    bugs: list[TaggedItem]
    issues: list[TaggedItem]
