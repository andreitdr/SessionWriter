from __future__ import annotations

import re

from .constants import DURATION_VALUES, START_RE
from .models import SessionFormData


def parse_start(value: str) -> tuple[int, int, int, int, int, str] | None:
    match = START_RE.match(value)
    if not match:
        return None

    month, day, year, hour, minute, ampm = match.groups()
    month_i = int(month)
    day_i = int(day)
    year_i = int(year)
    hour_i = int(hour)
    minute_i = int(minute)

    if month_i < 1 or month_i > 12:
        return None
    if day_i < 1 or day_i > 31:
        return None
    if hour_i < 1 or hour_i > 12:
        return None
    if minute_i < 0 or minute_i > 59:
        return None

    return (month_i, day_i, year_i, hour_i, minute_i, ampm.lower())


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not re.fullmatch(r"\d+", value):
        return None
    return int(value)


def session_filename(data: SessionFormData) -> str:
    start = parse_start(data.start)
    if start is None:
        return "invalid-start.ses"

    month, day, year, _, _, _ampm = start
    initials = data.initials.strip().upper()
    sequence = data.sequence.strip().upper()
    return f"ET-{initials}-{year:02d}{month:02d}{day:02d}-{sequence}.ses"


def validate_form(data: SessionFormData) -> list[str]:
    errors: list[str] = []

    initials = data.initials.strip().upper()
    if not re.fullmatch(r"\w{3}", initials):
        errors.append("Tester initials must be exactly 3 word characters (A-Z, 0-9, _).")

    sequence = data.sequence.strip().upper()
    if not re.fullmatch(r"\w", sequence):
        errors.append("Sequence must be a single word character (like A, B, C, 1).")

    if parse_start(data.start) is None:
        errors.append("Start must match m/d/yy h:mmam or m/d/yy h:mmpm and use valid ranges.")

    if not data.charter_description.strip():
        errors.append("Charter description is required.")

    if not data.selected_areas:
        errors.append("Add at least one area.")

    if not data.testers:
        errors.append("Add at least one tester name.")

    duration = data.duration.strip().lower()
    if duration not in DURATION_VALUES:
        errors.append("Duration must be short, normal, or long.")

    multiplier = parse_int(data.multiplier)
    if multiplier is None or multiplier < 1:
        errors.append("Duration multiplier must be an integer >= 1.")

    setup = parse_int(data.setup_pct)
    test = parse_int(data.test_pct)
    bug = parse_int(data.bug_pct)
    charter_pct = parse_int(data.charter_pct)
    opportunity_pct = parse_int(data.opportunity_pct)

    for label, value in (
        ("Session setup", setup),
        ("Test design and execution", test),
        ("Bug investigation and reporting", bug),
        ("Charter", charter_pct),
        ("Opportunity", opportunity_pct),
    ):
        if value is None or value < 0 or value > 100:
            errors.append(f"{label} percentage must be an integer 0-100.")

    if setup is not None and test is not None and bug is not None and (setup + test + bug) not in (99, 100):
        errors.append("Session setup + Test design/execution + Bug investigation must total 99 or 100.")

    if charter_pct is not None and opportunity_pct is not None and charter_pct + opportunity_pct != 100:
        errors.append("Charter % + Opportunity % must total 100.")

    for idx, bug_item in enumerate(data.bugs, start=1):
        if not bug_item.body.strip():
            errors.append(f"Bug item {idx} has no description.")

    for idx, issue_item in enumerate(data.issues, start=1):
        if not issue_item.body.strip():
            errors.append(f"Issue item {idx} has no description.")

    return errors
