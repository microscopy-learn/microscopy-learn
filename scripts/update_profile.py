"""Refresh the "Currently learning" section of the profile README from the
ai-engineering-journey weekly logs. GitHub Actions runs this daily; run it locally with
`python scripts/update_profile.py`, or `LOGS_DIR=path/to/logs python scripts/update_profile.py`
to test against local files.
"""

import json
import os
import re
import urllib.request
from pathlib import Path

OWNER, REPO = "microscopy-learn", "ai-engineering-journey"
README = Path(__file__).resolve().parent.parent / "README.md"
TOTAL_WEEKS = 52
START = "1 January 2027"
PHASES = {
    0: "Setup and orientation",
    1: "Python, maths and data foundations",
    2: "Classical machine learning",
    3: "Deep learning and transformers",
    4: "LLM apps, RAG and GraphRAG",
    5: "Agents, tool use, MCP and evals",
    6: "Production, LLMOps and fine-tuning",
    7: "Portfolio and job readiness",
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "profile-updater"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https URLs)
        return response.read()


def log_files() -> list[tuple[str, str]]:
    """Return (filename, text) for every logs/week-*.md file."""
    local = os.environ.get("LOGS_DIR")
    if local:
        return [(p.name, p.read_text(encoding="utf-8")) for p in Path(local).glob("week-*.md")]
    listing = json.loads(fetch(f"https://api.github.com/repos/{OWNER}/{REPO}/contents/logs"))
    files = [f for f in listing if re.match(r"week-.*\.md$", f["name"])]
    return [(f["name"], fetch(f["download_url"]).decode("utf-8")) for f in files]


def front_matter(text: str) -> dict:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    data = {}
    for line in (match.group(1).splitlines() if match else []):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip().lower()] = value.strip().strip('"').strip("'")
    return data


def to_number(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def render() -> str:
    entries = []
    for name, text in log_files():
        meta = front_matter(text)
        week, phase = to_number(meta.get("week")), to_number(meta.get("phase"))
        if week is not None and phase is not None:
            meta.update(week=int(week), phase=int(phase), name=name)
            entries.append(meta)
    repo_url = f"https://github.com/{OWNER}/{REPO}"
    if not entries:
        return f"Starting {START}. Follow along in [{REPO}]({repo_url})."
    entries.sort(key=lambda e: e["week"])
    latest = entries[-1]
    if latest["week"] < 1:
        return (
            f"**Starting {START}** · a 52-week plan, January 2027 to January 2028\n\n"
            "Setup done: project template, learning log and this auto-updating profile.\n\n"
            f"Follow along: [{REPO}]({repo_url})"
        )
    hours = sum(to_number(e.get("hours")) or 0 for e in entries if e["week"] >= 1)
    filled = round(20 * latest["week"] / TOTAL_WEEKS)
    lines = [
        f"**Week {latest['week']} of {TOTAL_WEEKS}** · Phase {latest['phase']}: "
        f"{PHASES.get(latest['phase'], '')}",
        "",
        f"`{'█' * filled}{'░' * (20 - filled)}` {round(100 * latest['week'] / TOTAL_WEEKS)}%"
        + (f" · {hours:g} hours so far" if hours else ""),
    ]
    if latest.get("theme"):
        lines += ["", f"This week: {latest['theme']}"]
    lines += [
        "",
        f"Latest log: [week {latest['week']:02d}]({repo_url}/blob/main/logs/{latest['name']}) · "
        f"Full progress: [{REPO}]({repo_url})",
    ]
    return "\n".join(lines)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(r"(<!-- JOURNEY:START -->).*?(<!-- JOURNEY:END -->)", re.S)
    if not pattern.search(text):
        raise SystemExit("README is missing the JOURNEY markers")
    updated = pattern.sub(lambda m: f"{m.group(1)}\n{render()}\n{m.group(2)}", text)
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print("Profile README updated")
    else:
        print("Profile README already up to date")


if __name__ == "__main__":
    main()
