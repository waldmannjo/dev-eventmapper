"""Compute the next Eventmapper version from commits since the last release tag.

Rule: the highest-ranked commit since the last `vX.Y.Z` tag decides the bump.

    BREAKING CHANGE footer or `type!:`  -> major  (output/CSV format, removed features)
    feat                                -> minor
    fix, harden, ui, refactor, perf     -> patch  (also any non-conventional subject)
    docs, test, chore, ci, build, style -> no release

Usage:
    python scripts/release.py              # dry run: show commits, bump and changelog draft
    python scripts/release.py --apply      # write VERSION + draft CHANGELOG entry into app.py
    python scripts/release.py --set 1.0.0  # explicit version instead of the computed one
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"

LEVELS = ["none", "patch", "minor", "major"]
NO_RELEASE_TYPES = {"docs", "test", "chore", "ci", "build", "style"}
MINOR_TYPES = {"feat"}
CHANGELOG_TYPES = {"feat", "fix", "harden", "ui", "perf"}

_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<desc>.+)$")
_VERSION_LINE = re.compile(r'^VERSION = "(\d+\.\d+\.\d+)"$', re.M)
_PR_SUFFIX = re.compile(r"\s*\(#\d+\)$")


def classify(subject, body=""):
    """Return (level, type, description) for one commit."""
    m = _SUBJECT.match(subject.strip())
    if not m:
        return "patch", None, subject.strip()
    ctype, desc = m["type"], m["desc"]
    if m["bang"] or re.search(r"^BREAKING[ -]CHANGE:", body, re.M):
        return "major", ctype, desc
    if ctype in MINOR_TYPES:
        return "minor", ctype, desc
    if ctype in NO_RELEASE_TYPES:
        return "none", ctype, desc
    return "patch", ctype, desc


def bump(version, level):
    """Apply a bump level to 'X.Y.Z'. While major is 0, breaking changes bump minor."""
    major, minor, patch = map(int, version.split("."))
    if level == "major" and major == 0:
        level = "minor"
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return version


def changelog_draft(commits):
    """User-facing draft lines from (level, type, desc) tuples; to be curated by hand."""
    lines = []
    for level, ctype, desc in commits:
        if level == "major" or ctype in CHANGELOG_TYPES:
            desc = _PR_SUFFIX.sub("", desc)
            lines.append(desc[:1].upper() + desc[1:])
    return lines


def insert_release(source, version, items):
    """Return app.py source with VERSION set and a new CHANGELOG entry on top."""
    source, n = _VERSION_LINE.subn(f'VERSION = "{version}"', source, count=1)
    if n != 1:
        raise ValueError("VERSION line not found in app.py")
    entry = f'    "{version}": [\n' + "".join(f"        {json.dumps(item, ensure_ascii=False)},\n" for item in items) + "    ],\n"
    marker = "CHANGELOG = {\n"
    if marker not in source:
        raise ValueError("CHANGELOG dict not found in app.py")
    return source.replace(marker, marker + entry, 1)


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def last_tag():
    try:
        return _git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*").strip()
    except subprocess.CalledProcessError:
        return None


def commits_since(tag):
    rev = f"{tag}..HEAD" if tag else "HEAD"
    raw = _git("log", rev, "--no-merges", "--format=%s%x1f%b%x1e")
    out = []
    for record in raw.split("\x1e"):
        if record.strip():
            subject, _, body = record.strip("\n").partition("\x1f")
            out.append((subject, body))
    return out


def _version_key(v):
    return tuple(map(int, v.split(".")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write VERSION and CHANGELOG draft into app.py")
    ap.add_argument("--set", metavar="X.Y.Z", help="use this version instead of the computed one")
    args = ap.parse_args(argv)

    source = APP.read_text(encoding="utf-8")
    current = _VERSION_LINE.search(source).group(1)
    tag = last_tag()
    if tag and tag != f"v{current}":
        print(f"warning: app.py VERSION {current} does not match last tag {tag}", file=sys.stderr)

    classified = [(*classify(s, b), s) for s, b in commits_since(tag)]
    print(f"Last release: {tag or '(no tag)'}  current VERSION: {current}\n")
    for level, _, _, subject in classified:
        print(f"  [{level:5}] {subject}")
    level = max((c[0] for c in classified), key=LEVELS.index, default="none")

    if args.set:
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.set) or _version_key(args.set) <= _version_key(current):
            sys.exit(f"--set must be X.Y.Z and greater than {current}")
        nxt = args.set
    else:
        nxt = bump(current, level)
    print(f"\nBump: {'set' if args.set else level}  ->  {nxt}")
    if nxt == current:
        print("Nothing to release (only docs/test/chore commits).")
        return 0

    items = changelog_draft([c[:3] for c in classified]) or ["TODO: describe this release"]
    print("\nChangelog draft:")
    for item in items:
        print(f"  - {item}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write app.py.")
        return 0
    APP.write_text(insert_release(source, nxt, items), encoding="utf-8")
    print(f"\nWrote VERSION {nxt} to app.py. Next steps:")
    print("  1. Curate the CHANGELOG lines (user-facing, English, merge related commits)")
    print(f"  2. git commit -am 'chore: release {nxt}'  -> PR -> merge into main")
    print(f"  3. git switch main && git pull && git tag v{nxt} && git push origin v{nxt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
