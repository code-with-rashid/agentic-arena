"""Report which tracing/telemetry env vars this crewai build actually reads."""

import pathlib
import re

import crewai

PATTERN = re.compile(
    r"""(?:getenv|environ\.get|environ\[)\(?["']([A-Z0-9_]*(?:TRACING|TELEMETRY|TRACE)[A-Z0-9_]*)"""
)

root = pathlib.Path(crewai.__file__).parent
seen: set[str] = set()
for path in root.rglob("*.py"):
    seen.update(PATTERN.findall(path.read_text(errors="ignore")))
print("tracing/telemetry env vars crewai reads:", sorted(seen))

# Where does the interactive trace prompt come from?
for path in root.rglob("*.py"):
    text = path.read_text(errors="ignore")
    if "view your execution traces" in text or "Execution Traces" in text:
        print("prompt emitted from:", path.relative_to(root))
