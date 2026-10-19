"""
Second step-4 download (plan change 5): the plain headerless CSV feeds a
downstream import and keeps its format, so the explanation columns go into
a separate "Download with explanation" file with headers and every column.
"""
import csv
import io

import pandas as pd
import pytest

from app import _explanation_csv, _explanation_mapping_filename


def _display_df():
    return pd.DataFrame({
        "Event code": ["1"], "Reason code": ["2"], "AEB event code": ["ARR"],
        "Event description": ["Empfänger nicht angetroffen"],
        "confidence": [0.9], "source": ["emb+ce"],
        "candidates": ["ARR 0.95\nDEL 0.10"], "knn_matches": [""], "reasoning": [""],
        "needs_review": [False],
    })


def test_explanation_csv_has_header_and_every_column():
    text = _explanation_csv(_display_df()).decode("utf-8-sig")

    assert text == (
        "Event code;Reason code;AEB event code;Event description;confidence;source;"
        "candidates;knn_matches;reasoning;needs_review\n"
        '1;2;ARR;Empfänger nicht angetroffen;0.9;emb+ce;"ARR 0.95\nDEL 0.10";;;False\n'
    )


def test_explanation_csv_starts_with_utf8_bom():
    # Without a BOM, Excel decodes the file as ANSI and garbles umlauts in carrier texts.
    assert _explanation_csv(_display_df()).startswith(b"\xef\xbb\xbf")


def test_explanation_filename_with_identcode():
    assert _explanation_mapping_filename("DPD") == "final_mapping_DPD_explained.csv"


def test_explanation_filename_without_identcode():
    assert _explanation_mapping_filename(None) == "final_mapping_explained.csv"


def test_step4_offers_both_downloads(real_streamlit):
    at = real_streamlit.from_file("app.py", default_timeout=60)
    at.session_state["current_step"] = 4
    at.session_state["df_final"] = pd.DataFrame({
        "Description": ["Package arrived at depot"], "final_code": ["ARR"],
        "confidence": [0.9], "source": ["emb+ce"], "needs_review": [False],
    })
    at.run()
    at.sidebar.text_input[0].input("sk-dummy").run()

    assert not at.exception
    labels = [e.proto.label for e in at.get("download_button")]
    assert len(labels) == 2
    assert "Download Mapping" in labels[0]
    assert "Download with explanation" in labels[1]


def _parse(data, delimiter):
    """Parse the export as Excel would with the given list separator."""
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=delimiter))


def _formula_cells(rows):
    return [c for row in rows for c in row if c.strip(' "').startswith(("=", "+", "-", "@"))]


def test_explanation_csv_neutralises_formula_cells():
    # Carrier texts and LLM output must not run as formulas when the file opens in Excel.
    df = _display_df()
    df["Event description"] = ["=HYPERLINK(\"http://x\")"]
    df["reasoning"] = ["@SUM(1)"]
    df["knn_matches"] = ["+1"]
    df["candidates"] = ["-1"]

    row = _parse(_explanation_csv(df), ";")[1]

    assert row[3] == "'=HYPERLINK(\"http://x\")"
    assert row[6:9] == ["'-1", "'+1", "'@SUM(1)"]
    assert row[4] == "0.9"  # numbers untouched


@pytest.mark.parametrize("text", [
    "Zustellung,=1+1", "Zustellung, =1+1", "Zustellung\n-1+1",
    'Zustellung,"=1+1', 'Zustellung, " =1+1', '"=1+1',
])
def test_explanation_csv_safe_when_excel_splits_on_comma(text):
    # Excel on an English locale splits on "," instead of ";"
    df = _display_df()
    df["Event description"] = [text]

    assert _formula_cells(_parse(_explanation_csv(df), ",")) == []


@pytest.mark.parametrize("delimiter", [";", ","])
@pytest.mark.parametrize("column", ["Event code", "Event description"])
def test_explanation_csv_safe_with_quotes_before_formula(column, delimiter):
    # A quote between the separator and the formula character must not hide it,
    # in the first column too, on both ";" and "," locales.
    df = _display_df()
    df[column] = ['"=1+1']

    assert _formula_cells(_parse(_explanation_csv(df), delimiter)) == []


def test_explanation_csv_neutralises_string_dtype_columns():
    # pandas 3 stores text as the "str"/"string" dtype, not object
    df = _display_df()
    df["reasoning"] = pd.array(["=1+1"], dtype="string")

    assert _parse(_explanation_csv(df), ";")[1][8] == "'=1+1"


def test_explanation_csv_neutralises_column_names():
    df = _display_df().rename(columns={"reasoning": "=cmd"})

    assert _parse(_explanation_csv(df), ";")[0][8] == "'=cmd"
