import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import _candidates_to_df


def test_candidates_to_df_has_include_column():
    df = _candidates_to_df([{"name": "A", "description": "d", "context": "c"}])
    assert "_include" in df.columns


def test_candidates_to_df_include_defaults_true():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    assert df["_include"].all()


def test_candidates_to_df_empty_has_include_column():
    df = _candidates_to_df([])
    assert "_include" in df.columns


def test_candidates_to_df_column_order():
    df = _candidates_to_df([{"name": "A"}])
    assert list(df.columns[:2]) == ["_select", "_include"]


def test_include_filtering():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}, {"name": "C"}])
    df.loc[df["name"] == "B", "_include"] = False
    selected = df[df["_include"]]["name"].tolist()
    assert selected == ["A", "C"]


def test_include_filtering_all_unchecked():
    df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    df["_include"] = False
    selected = df[df["_include"]]["name"].tolist()
    assert selected == []


def test_include_filtering_empty_df():
    # Empty DataFrame with _include column — filter returns [] natively, no KeyError
    df = _candidates_to_df([])
    selected = df[df["_include"]]["name"].tolist()
    assert selected == []


def test_include_survives_move():
    """_include state is preserved when rows are moved between tables (mimics move button logic)."""
    stat_df = _candidates_to_df([{"name": "A"}, {"name": "B"}])
    reas_df = _candidates_to_df([{"name": "C"}])

    # User unchecks Include on B, then moves B to Reason
    stat_df.loc[stat_df["name"] == "B", "_include"] = False
    stat_df.loc[stat_df["name"] == "B", "_select"] = True

    sel = stat_df["_select"].astype(bool)
    to_move = stat_df[sel].drop(columns=["_select"])
    remaining = stat_df[~sel].drop(columns=["_select"])
    remaining.insert(0, "_select", False)
    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    reas_df_updated = pd.concat([reas_df, to_move_with_sel], ignore_index=True)

    # B is now in reas with _include=False preserved
    b_row = reas_df_updated[reas_df_updated["name"] == "B"]
    assert not b_row.empty
    assert b_row.iloc[0]["_include"] == False

    # A remains in stat with _include=True
    assert remaining.iloc[0]["_include"] == True
