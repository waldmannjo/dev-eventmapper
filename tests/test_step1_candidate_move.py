"""Tests for Step 1 candidate-move helper logic (DataFrame manipulation)."""
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _candidates_to_df


def test_candidates_to_df_columns():
    candidates = [{"name": "Table 1", "description": "Status codes", "context": "Page 2"}]
    df = _candidates_to_df(candidates)
    assert list(df.columns) == ["_select", "name", "description", "context"]
    assert df.iloc[0]["name"] == "Table 1"
    assert df.iloc[0]["_select"] == False


def test_candidates_to_df_empty():
    df = _candidates_to_df([])
    assert df.empty
    assert list(df.columns) == ["_select", "name", "description", "context"]


def test_candidates_to_df_missing_optional_fields():
    candidates = [{"name": "Table X"}]
    df = _candidates_to_df(candidates)
    assert df.iloc[0]["description"] == ""
    assert df.iloc[0]["context"] == ""


def test_move_selected_candidate_to_other_df():
    stat_df = _candidates_to_df([
        {"name": "Table 1", "description": "Status"},
        {"name": "Table 2", "description": "Status 2"},
    ])
    reas_df = _candidates_to_df([{"name": "Table 3", "description": "Reason"}])

    # Simulate user selecting Table 1 for move
    stat_df.loc[0, "_select"] = True

    to_move = stat_df[stat_df["_select"]].drop(columns=["_select"])
    remaining = stat_df[~stat_df["_select"]].drop(columns=["_select"])

    assert len(remaining) == 1
    assert remaining.iloc[0]["name"] == "Table 2"

    to_move_with_sel = to_move.copy()
    to_move_with_sel.insert(0, "_select", False)
    remaining.insert(0, "_select", False)
    reas_df_updated = pd.concat([reas_df, to_move_with_sel], ignore_index=True)

    assert len(reas_df_updated) == 2
    assert reas_df_updated.iloc[1]["name"] == "Table 1"


def test_no_selection_move_is_noop():
    stat_df = _candidates_to_df([{"name": "Table 1"}])
    to_move = stat_df[stat_df["_select"]]
    assert to_move.empty  # UI should warn and abort


def test_moving_all_status_rows_detected():
    stat_df = _candidates_to_df([{"name": "Table 1"}])
    stat_df.loc[0, "_select"] = True
    remaining = stat_df[~stat_df["_select"]]
    assert remaining.empty  # UI should block: at least one status source required
