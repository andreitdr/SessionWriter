from __future__ import annotations

from .constants import SEPARATOR
from .models import SessionFormData
from .validation import parse_start

def _section(title: str, lines: list[str]) -> list[str]:
    return [title, SEPARATOR, *lines, ""]


def build_content(data: SessionFormData) -> str:
    charter_description_lines = [line.rstrip() for line in data.charter_description.splitlines() if line.rstrip()]
    testers = [name.strip() for name in data.testers if name.strip()]

    duration = data.duration.strip().lower()
    multiplier = int(data.multiplier.strip())
    duration_line = duration if multiplier == 1 else f"{duration} * {multiplier}"

    data_files_lines = data.datafiles[:] if data.datafiles else ["#N/A"]

    notes_raw = data.notes.strip("\n")
    if notes_raw.strip():
        notes_lines = [line.rstrip() for line in notes_raw.splitlines() if line.rstrip()]
    else:
        notes_lines = ["#N/A"]

    if not data.bugs:
        bugs_lines = ["#N/A"]
    else:
        bugs_lines: list[str] = []
        for idx, bug in enumerate(data.bugs, start=1):
            bugs_lines.append(f"#BUG {idx}")
            bugs_lines.extend(line.rstrip() for line in bug.body.splitlines())
            bugs_lines.append("")
        while bugs_lines and bugs_lines[-1] == "":
            bugs_lines.pop()

    if not data.issues:
        issues_lines = ["#N/A"]
    else:
        issues_lines: list[str] = []
        for idx, issue in enumerate(data.issues, start=1):
            issues_lines.append(f"#ISSUE {idx}")
            issues_lines.extend(line.rstrip() for line in issue.body.splitlines())
            issues_lines.append("")
        while issues_lines and issues_lines[-1] == "":
            issues_lines.pop()

    version_lines = [f"VERSION | {v}" for v in data.versions]
    environment_lines = [f"ENVIRONMENT | {e}" for e in data.environments]

    parts: list[str] = []
    parts.extend(_section("CHARTER", [
        *charter_description_lines,
        "",
        "#AREAS",
        *data.selected_areas,
        "",
        *version_lines,
        *environment_lines,
    ]))
    
    start_line = data.start.strip().lower()
    parsed_start = parse_start(start_line)
    if parsed_start:
        month, day, year, hour, minute, ampm = parsed_start
        start_line = f"{month:02d}/{day:02d}/{year:02d} {hour}:{minute:02d}{ampm}"
        
    parts.extend(_section("START", [start_line]))
    parts.extend(_section("TESTER", testers))
    parts.extend(
        _section(
            "TASK BREAKDOWN",
            [
                "#DURATION",
                duration_line,
                "",
                "#SESSION SETUP",
                data.setup_pct.strip(),
                "",
                "#TEST DESIGN AND EXECUTION",
                data.test_pct.strip(),
                "",
                "#BUG INVESTIGATION AND REPORTING",
                data.bug_pct.strip(),
                "",
                "#CHARTER VS. OPPORTUNITY",
                f"{data.charter_pct.strip()}/{data.opportunity_pct.strip()}",
            ],
        )
    )
    parts.extend(_section("DATA FILES", data_files_lines))
    parts.extend(_section("TEST NOTES", notes_lines))
    parts.extend(_section("BUGS", bugs_lines))
    parts.extend(_section("ISSUES", issues_lines))

    return "\n".join(parts).rstrip() + "\n"
