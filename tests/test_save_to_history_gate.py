"""
Save-to-History stays hidden until the ingestion design is settled.

LLM self-reported confidence does not separate good from bad mappings well
enough to gate history writes (one 1.5k-row run would have added ~1.1k
unreviewed rows), so the panel must not appear even for rows that pass
the confidence gate.
"""
import pandas as pd


def test_save_to_history_panel_hidden_for_confident_llm_rows(real_streamlit):
    AppTest = real_streamlit
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["current_step"] = 4
    at.session_state["df_final"] = pd.DataFrame({
        "Statuscode": ["1"],
        "Reasoncode": ["2"],
        "Description": ["Package arrived at depot"],
        "final_code": ["ARR"],
        "confidence": [0.95],
        "source": ["llm-batch"],
    })
    at.run()
    at.sidebar.text_input[0].input("sk-dummy").run()

    assert not at.exception
    assert any(h.value.startswith("✅ Step 4") for h in at.header), "step 4 must render"
    assert not any("Save to History" in b.label for b in at.button)
