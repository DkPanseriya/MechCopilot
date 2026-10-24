"""Card edits: inputs changed in a calculator card are stored with the reply and reach the copilot."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from copilot import _given_inputs, _history_text, edit_summary, normalise_tools
from routers.sessions import ToolEdit, edit_tool, get_session


def _bearing_tool():
    tools, _ = normalise_tools({"tools": [{"calculator": "bearing_selector", "inputs": {
        "Fr": {"value": 3.5, "unit": "kN", "source": "user"}, "n": {"value": 1450, "source": "user"},
        "bore_min": {"value": 30, "source": "user"}, "bore_max": {"value": 30, "source": "user"}}}]})
    return tools[0]


def test_edit_summary_reruns_and_lists_only_changed_inputs():
    tool = _bearing_tool()
    edited = edit_summary(tool, {**tool["inputs"], "Fr": {"value": 9000, "unit": "N"}})
    assert edited["changed"] == ["Fr"]
    assert edited["inputs"] == {"Fr": {"value": 9000, "unit": "N"}}
    assert edited["verdict"] == "fail"                    # no 30 mm deep groove bearing carries 9 kN


def test_same_value_in_another_unit_is_not_a_change():
    tool = _bearing_tool()
    edited = edit_summary(tool, {**tool["inputs"], "Fr": {"value": 3500, "unit": "N"}})
    assert edited["changed"] == []


def test_history_carries_the_edit_and_the_new_verdict():
    tool = _bearing_tool()
    tool["edited"] = edit_summary(tool, {**tool["inputs"], "Fr": {"value": 9, "unit": "kN"}})
    text = _history_text([{"role": "assistant", "content": "Use a 6206.", "tool_data": {"tools": [tool]}}])
    assert "Fr=9 kN (edited in card)" in _given_inputs(tool)
    assert "[user edited Bearing finder: Radial load Fr 3.5 kN → 9 kN; verdict now fail" in text


@pytest.fixture
def stored():
    """An in-memory database holding one session with one assistant reply."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    sess = database.Session(title="t")
    db.add(sess)
    db.commit()
    msg = database.Message(session_id=sess.id, role="assistant", content="Use a 6206.",
                           tool_data={"tools": [_bearing_tool()]})
    db.add(msg)
    db.commit()
    yield db, sess.id, msg.id
    db.close()


def test_patch_stores_the_edit_on_the_reply(stored):
    db, sid, mid = stored
    tool = _bearing_tool()
    out = edit_tool(sid, mid, 0, ToolEdit(calculator="bearing_selector",
                                          inputs={**tool["inputs"], "Fr": {"value": 9, "unit": "kN"}}), db)
    assert out["changed"] == ["Fr"]
    msg = get_session(sid, db)["messages"][0]
    assert msg.id == mid
    assert msg.tool_data["tools"][0]["edited"]["verdict"] == "fail"


def test_patch_rejects_wrong_calculator_and_bad_inputs(stored):
    db, sid, mid = stored
    with pytest.raises(HTTPException) as wrong:
        edit_tool(sid, mid, 0, ToolEdit(calculator="bolted_joint", inputs={}), db)
    assert wrong.value.status_code == 404
    with pytest.raises(HTTPException) as bad:
        edit_tool(sid, mid, 0, ToolEdit(calculator="bearing_selector", inputs={"btype": "not_a_type"}), db)
    assert bad.value.status_code == 422
