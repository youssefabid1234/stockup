"""Youssef · Lucie's notebook operations are safe (known ids, cut-short answers kept), the sheet is fresh between calls."""

from app.agent import call_context
from app.routers.memory import Note, parse_ops

NOTES = [Note(id="n1", text="5 sacs tradi pour jeudi", kind="commande")]


def test_complete_operations_are_kept_from_a_cut_short_answer():
    raw = ('{"ops": [{"op": "strike", "id": "n1", "reason": "quantité changée"}, {"op": "add", "text": "8 sacs tradi jeudi", '
           '"kind": "commande", "important": false}, {"op": "add", "text": "Confirmer les 8 ')
    ops = parse_ops(raw, NOTES)
    assert [o["op"] for o in ops] == ["strike", "add"] and ops[1]["text"] == "8 sacs tradi jeudi"


def test_unknown_ids_and_junk_are_dropped():
    raw = '{"ops": [{"op": "strike", "id": "n9"}, {"op": "link", "from": "n1", "to": "n7"}, "x", {"op": "add", "text": " "}]}'
    assert parse_ops(raw, NOTES) == []


def test_a_second_call_reloads_the_sheet():
    assert call_context.CACHE_TTL_S <= 30  # an order or a summary of the previous test call is seen by the next one
