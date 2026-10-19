import ast
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from release import APP, bump, changelog_draft, classify, insert_release


@pytest.mark.parametrize("subject, body, level", [
    ("feat: carrier identcode", "", "minor"),
    ("feat(ui): select all", "", "minor"),
    ("fix: multi file upload (#8)", "", "patch"),
    ("harden: defused XML parsing", "", "patch"),
    ("ui: rename Step 4 columns", "", "patch"),
    ("refactor: loader cleanup", "", "patch"),
    ("docs: onboarding page", "", "none"),
    ("chore: update models", "", "none"),
    ("test: tighten assertions", "", "none"),
    ("kein openai key beim starten", "", "patch"),
    ("feat!: drop CSV header row", "", "major"),
    ("ui: drop CSV header", "BREAKING CHANGE: final CSV has no header", "major"),
])
def test_classify(subject, body, level):
    assert classify(subject, body)[0] == level


@pytest.mark.parametrize("version, level, expected", [
    ("1.2.3", "major", "2.0.0"),
    ("1.2.3", "minor", "1.3.0"),
    ("1.2.3", "patch", "1.2.4"),
    ("1.2.3", "none", "1.2.3"),
    ("0.6.0", "major", "0.7.0"),
    ("0.6.0", "patch", "0.6.1"),
])
def test_bump(version, level, expected):
    assert bump(version, level) == expected


def test_changelog_draft_keeps_user_facing_types_only():
    commits = [classify(s) for s in [
        "feat: multiple file upload (#8)", "docs: notes", "refactor: x", "fix: re-extract on change",
    ]]
    assert changelog_draft(commits) == ["Multiple file upload", "Re-extract on change"]


def test_insert_release_updates_version_and_prepends_entry():
    src = 'VERSION = "1.0.0"\n\nCHANGELOG = {\n    "1.0.0": [\n        "Old",\n    ],\n}\n'
    out = insert_release(src, "1.1.0", ['New "quoted" thing'])
    ns = {}
    exec(out, ns)
    assert ns["VERSION"] == "1.1.0"
    assert list(ns["CHANGELOG"]) == ["1.1.0", "1.0.0"]
    assert ns["CHANGELOG"]["1.1.0"] == ['New "quoted" thing']


def _app_assignments():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    return {
        t.id: ast.literal_eval(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name) and t.id in ("VERSION", "CHANGELOG")
    }


def test_app_version_matches_newest_changelog_entry():
    a = _app_assignments()
    assert next(iter(a["CHANGELOG"])) == a["VERSION"]


def test_app_changelog_is_strictly_descending():
    keys = [tuple(map(int, v.split("."))) for v in _app_assignments()["CHANGELOG"]]
    assert keys == sorted(keys, reverse=True) and len(set(keys)) == len(keys)
