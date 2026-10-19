import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
import release
from release import (APP, bump, changelog_draft, classify, gh_release_cmd, insert_release,
                     read_app_release, release_notes)


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
    version, changelog = read_app_release(APP.read_text(encoding="utf-8"))
    return {"VERSION": version, "CHANGELOG": changelog}


def test_app_version_matches_newest_changelog_entry():
    a = _app_assignments()
    assert next(iter(a["CHANGELOG"])) == a["VERSION"]


def test_app_changelog_is_strictly_descending():
    keys = [tuple(map(int, v.split("."))) for v in _app_assignments()["CHANGELOG"]]
    assert keys == sorted(keys, reverse=True) and len(set(keys)) == len(keys)


def test_app_changelog_has_no_uncurated_placeholder():
    items = [i for entries in _app_assignments()["CHANGELOG"].values() for i in entries]
    assert not [i for i in items if i.startswith("TODO")]


def test_release_notes_lists_entry_items():
    changelog = {"1.1.0": ["New thing", "Fixed thing"], "1.0.0": ["Old"]}
    assert release_notes(changelog, "1.1.0") == "- New thing\n- Fixed thing\n"


@pytest.mark.parametrize("changelog", [{"1.0.0": ["Old"]}, {"1.1.0": []}, {"1.1.0": ["TODO: describe"]}])
def test_release_notes_rejects_missing_or_uncurated_entry(changelog):
    with pytest.raises(ValueError):
        release_notes(changelog, "1.1.0")


def test_gh_release_cmd_targets_existing_tag():
    cmd = gh_release_cmd("1.1.0", "- New\n")
    assert cmd[:4] == ["gh", "release", "create", "v1.1.0"]
    assert "--verify-tag" in cmd
    assert cmd[cmd.index("--title") + 1] == "Eventmapper 1.1.0"
    assert cmd[cmd.index("--notes") + 1] == "- New\n"


def test_publish_runs_gh_with_notes_from_app(monkeypatch):
    calls = []
    monkeypatch.setattr(release.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or type("R", (), {"returncode": 0})())
    assert release.main(["--publish"]) == 0
    a = _app_assignments()
    assert calls == [gh_release_cmd(a["VERSION"], release_notes(a["CHANGELOG"], a["VERSION"]))]


def test_publish_exits_when_gh_fails(monkeypatch):
    monkeypatch.setattr(release.subprocess, "run", lambda cmd, **kw: type("R", (), {"returncode": 1})())
    with pytest.raises(SystemExit):
        release.main(["--publish"])


def test_publish_rejects_apply_combination():
    with pytest.raises(SystemExit):
        release.main(["--publish", "--apply"])
