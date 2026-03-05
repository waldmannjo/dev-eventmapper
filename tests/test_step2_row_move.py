"""Tests for Step 2 row-move helper logic (DataFrame manipulation)."""
import pandas as pd
import io
from backend.extractor import preview_csv_string


def _df_with_select(csv_str: str) -> pd.DataFrame:
    """Reproduce the initialization logic: parse CSV and add _select column."""
    df = preview_csv_string(csv_str)
    df.insert(0, "_select", False)
    return df


def test_init_adds_select_column():
    csv = "Statuscode;Beschreibung\n10;Abholung\n20;Zustellung"
    df = _df_with_select(csv)
    assert "_select" in df.columns
    assert list(df["_select"]) == [False, False]


def test_move_selected_rows_to_other_table():
    csv_status = "Statuscode;Beschreibung\n10;Abholung\n20;Zustellung"
    csv_reason = "Reasoncode;Beschreibung\n01;Empf. nicht anwesend"

    df_s = _df_with_select(csv_status)
    df_r = _df_with_select(csv_reason)

    # Simulate user selecting row 0 in status table
    df_s.loc[0, "_select"] = True

    to_move = df_s[df_s["_select"]].drop(columns=["_select"])
    remaining = df_s[~df_s["_select"]].drop(columns=["_select"])

    assert len(remaining) == 1
    assert remaining.iloc[0]["Statuscode"] == 20

    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    df_r_updated = pd.concat([df_r, to_move_with_sel], ignore_index=True)

    # Reason table now has 2 rows: original + moved
    assert len(df_r_updated) == 2


def test_serialize_back_to_csv():
    csv_status = "Statuscode;Beschreibung\n10;Abholung"
    df_s = _df_with_select(csv_status)

    clean = df_s.drop(columns=["_select"], errors="ignore")
    result_csv = clean.to_csv(index=False, sep=";")

    # Round-trip: re-parse and verify
    df_back = pd.read_csv(io.StringIO(result_csv), sep=";")
    assert "_select" not in df_back.columns
    assert list(df_back.columns) == ["Statuscode", "Beschreibung"]
    assert df_back.iloc[0]["Statuscode"] == 10


def test_move_all_status_rows_is_blocked_by_empty_check():
    """Remaining must not be empty — this is enforced in the UI by an error message.
    Verify the detection logic itself."""
    csv_status = "Statuscode;Beschreibung\n10;Abholung"
    df_s = _df_with_select(csv_status)
    df_s.loc[0, "_select"] = True

    remaining = df_s[~df_s["_select"]].drop(columns=["_select"])
    assert remaining.empty  # UI should show error and block the move
