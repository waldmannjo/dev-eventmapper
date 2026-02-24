"""Tests for normalize_input() — the carrier text normalization function."""
import pytest
from backend.mapper import normalize_input


def test_lowercase():
    """normalize_input lowercases the entire string."""
    result = normalize_input("Package ARRIVED at Depot")
    assert result == result.lower()


def test_timestamp_removal_with_space():
    """normalize_input removes ISO-8601 timestamps with space separator."""
    text = "scan 2026-02-17 14:30:00 arrived"
    result = normalize_input(text)
    assert "2026-02-17" not in result
    assert "14:30" not in result
    assert "arrived" in result


def test_timestamp_removal_with_T():
    """normalize_input removes ISO-8601 timestamps with T separator."""
    text = "event 2025-12-01T09:00:00 departed"
    result = normalize_input(text)
    assert "2025-12-01" not in result
    assert "09:00" not in result
    assert "departed" in result


def test_timestamp_removal_without_seconds():
    """normalize_input removes timestamps that have no seconds component."""
    text = "scan 2026-01-15 08:45 processed"
    result = normalize_input(text)
    assert "2026-01-15" not in result
    assert "08:45" not in result
    assert "processed" in result


def test_tracking_id_removal():
    """normalize_input removes long alphanumeric tracking IDs (>=10 chars)."""
    text = "shipment JD014600006278590000 delivered"
    result = normalize_input(text)
    assert "JD014600006278590000" not in result
    assert "delivered" in result


def test_tracking_id_short_kept():
    """normalize_input does NOT remove short tokens (fewer than 10 chars)."""
    text = "code ABC123 arrived"
    result = normalize_input(text)
    # 'abc123' is only 6 chars — should survive
    assert "abc123" in result


def test_synonym_lkw():
    """normalize_input expands 'lkw' to 'truck'."""
    result = normalize_input("LKW arrived at depot")
    assert "truck" in result
    assert "lkw" not in result


def test_synonym_depot():
    """normalize_input normalizes 'depot' to 'facility'."""
    result = normalize_input("Package arrived at depot")
    assert "facility" in result
    assert "depot" not in result


def test_synonym_terminal():
    """normalize_input normalizes 'terminal' to 'facility'."""
    result = normalize_input("Scan at terminal")
    assert "facility" in result
    assert "terminal" not in result


def test_synonym_hub():
    """normalize_input normalizes 'hub' to 'facility'."""
    result = normalize_input("Transfer at hub complete")
    assert "facility" in result
    assert "hub" not in result


def test_synonym_sortierzentrum():
    """normalize_input normalizes 'sortierzentrum' to 'facility'."""
    result = normalize_input("Sortierzentrum eingang")
    assert "facility" in result
    assert "sortierzentrum" not in result


def test_synonym_lager():
    """normalize_input normalizes 'lager' to 'facility'."""
    result = normalize_input("Im Lager eingetroffen")
    assert "facility" in result
    assert "lager" not in result


def test_abbreviation_empf():
    """normalize_input expands 'empf.' to 'empfänger'."""
    result = normalize_input("Empf. nicht angetroffen")
    assert "empfänger" in result
    assert "empf." not in result


def test_abbreviation_zust():
    """normalize_input expands 'zust.' to 'zustellung'."""
    result = normalize_input("Zust. erfolgreich")
    assert "zustellung" in result
    assert "zust." not in result


def test_abbreviation_abh():
    """normalize_input expands 'abh.' to 'abholung'."""
    result = normalize_input("Abh. durch Fahrer")
    assert "abholung" in result
    assert "abh." not in result


def test_abbreviation_sendg():
    """normalize_input expands 'sendg.' to 'sendung'."""
    result = normalize_input("Sendg. verloren")
    assert "sendung" in result
    assert "sendg." not in result


def test_abbreviation_lfg():
    """normalize_input expands 'lfg.' to 'lieferung'."""
    result = normalize_input("Lfg. abgeschlossen")
    assert "lieferung" in result
    assert "lfg." not in result


def test_synonym_avis():
    """normalize_input normalizes 'avis' to 'notification'."""
    result = normalize_input("Avis gesendet")
    assert "notification" in result
    assert "avis" not in result


def test_synonym_aviso():
    """normalize_input normalizes 'aviso' to 'notification' without producing 'notificationo'."""
    result = normalize_input("Aviso an Empfänger")
    assert "notification" in result
    assert "aviso" not in result
    # Guard against the substring-replacement bug: "avis"->"notification" inside
    # "aviso" would yield "notificationo" instead of "notification".
    assert "notificationo" not in result
    assert result.startswith("notification an")


def test_compound_word_not_corrupted():
    """German compound words containing synonym substrings must not be corrupted."""
    result = normalize_input("Verlagerung ins Depot")
    # The compound word "Verlagerung" contains "lager" but must be preserved intact.
    assert "verlagerung" in result
    # The buggy plain str.replace() would turn it into "verfacilityung".
    assert "verfacilityung" not in result
    # Standalone "depot" IS a full word and should be replaced.
    assert "facility" in result
    assert "depot" not in result


def test_combined_normalization():
    """normalize_input handles multiple normalizations in one string."""
    text = "LKW 2026-02-17 14:30:00 JD014600006278590000 Depot eingang Empf. abwesend"
    result = normalize_input(text)
    assert "truck" in result
    assert "facility" in result
    assert "empfänger" in result
    assert "lkw" not in result
    assert "depot" not in result
    assert "empf." not in result
    assert "2026-02-17" not in result
    assert "JD014600006278590000" not in result


def test_strip_whitespace():
    """normalize_input strips leading/trailing whitespace from result."""
    result = normalize_input("  Paket angekommen  ")
    assert result == result.strip()


def test_empty_string():
    """normalize_input handles an empty string gracefully."""
    result = normalize_input("")
    assert result == ""
