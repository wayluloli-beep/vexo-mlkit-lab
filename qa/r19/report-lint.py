"""Summarize the private Android check without emitting snippets or machine paths."""
from pathlib import Path
from xml.etree.ElementTree import parse
import sys

source = Path(sys.argv[1]).resolve()
xml = source / "app/build/reports/lint-results-debug.xml"
if not xml.is_file():
    print("VEXO_LINT: no XML lint report")
    sys.exit(0)

def relative(path):
    p = Path(path)
    try:
        return str(p.relative_to(source)) if p.is_absolute() else path
    except ValueError:
        return "(external)"

issues = parse(xml).getroot().findall("issue")
for issue in issues:
    if issue.get("severity") not in {"Fatal", "Error", "Warning"}:
        continue
    loc = issue.find("location")
    loc = loc.attrib if loc is not None else {}
    print(f"VEXO_LINT: {issue.get('severity')} {issue.get('id')} {relative(loc.get('file', ''))}:{loc.get('line', '-')}")
