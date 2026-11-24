"""TEAM_EARLY_SPEECH: the reply is spoken while the model writes it, never a note written before a tool call."""

from app.services.voice_reply import EarlySpeech


def run(deltas, final, tool_after=None):
    said = []
    e = EarlySpeech(said.append, lambda s: s)
    for i, d in enumerate(deltas):
        if i == tool_after:
            e.tool_call()
        e.text(d)
    return said, e.rest(final)


def test_sentences_are_said_as_soon_as_the_next_one_starts_and_the_question_waits():
    deltas = ["Le tourage AOP est ", "en rupture. ", "J'ai le tourage 82 %", ", à 8 euros 46 le kilo. ", "Je vous le mets à la place ?"]
    final = "Le tourage AOP est en rupture. J'ai le tourage 82 %, à 8 euros 46 le kilo. Je vous le mets à la place ?"
    said, rest = run(deltas, final)
    assert said == ["Le tourage AOP est en rupture.", "J'ai le tourage 82 %, à 8 euros 46 le kilo."]
    assert rest == "Je vous le mets à la place ?"


def test_a_decimal_point_is_not_the_end_of_a_sentence():
    said, rest = run(["Il est à 8.46 le kilo", " en promo. Vous en voulez combien ?"], "Il est à 8.46 le kilo en promo. Vous en voulez combien ?")
    assert said == ["Il est à 8.46 le kilo en promo."] and rest == "Vous en voulez combien ?"


def test_a_note_before_a_tool_call_is_never_said():
    deltas = ["Je regarde. ", "", "Oui, il en reste. ", "Vous en voulez combien ?"]
    said, rest = run(deltas, "Oui, il en reste. Vous en voulez combien ?", tool_after=1)
    # « Je regarde. » was complete but not followed by more text of its step: dropped at the tool call
    assert said == ["Oui, il en reste."] and rest == "Vous en voulez combien ?"


def test_an_internal_note_stops_early_speech_for_the_turn():
    said, rest = run(["Le client demande du tourage. ", "Le tourage AOP est en rupture. ", "Autre chose ?"],
                     "Le tourage AOP est en rupture. Autre chose ?")
    assert said == [] and rest == "Le tourage AOP est en rupture. Autre chose ?"


def test_codes_are_never_said_early_and_the_end_is_said_once():
    said, rest = run(["Votre commande CMD-2026-007543 est validée. ", "Bonne journée !"],
                     "Votre commande est validée. Bonne journée !")
    assert said == ["Votre commande est validée."] and rest == "Bonne journée !"
