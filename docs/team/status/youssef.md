# Youssef – 的 Several brains (orchestrator, preloaded plug, super tool) · updated Tue. 24/11

- Done since the last sync:
  - **"Who calls?" before call** (PR #9): 1re replica S01 7,7 s → 3,5 s (/chat), 6,9 s → 3,9 s in voice.
  - **Corrected: "the agent forgets who calls during the call"** (see team test). Two causes:
    1. in which had not `TEAM_PRELOAD=1` in his `.env`, the name was on top but the card was not
       given to agent → **The caller chosen in the form is now always transmitted** (without switch);
    2. if the AI service restarts at full call (git pull, saved file: uvicorn --reload), it loses
       the appellant → ** the page returns the appellant to each ** reconnection (`resume`, the on-screen conversation is kept).
    Verified in real life: switch off + restart in full call → the agent still knows "Nadine Sarrailh".
  - Cache sheet copied by call (Guy then Nadine for the same bakery no longer mix).
  - **T1 super tool product (`product_insight`)** : stock + arrivals + customer price + classed replacements (rules of
    Daycem) with price and promo, on one call. 1re replica : S05 6,2 → 3,9 s, S40 4,3 → 3,4 s, S04 4,1 → 3,5 s
    (median); the agent quotes the exact promo. Ignited by default in `.env.example`.
  - **Free hands (Voices page, idea 1 + 2)** : no need to maintain Space: the microphone remains open, beginning and end of speech detected (pause ≈ 0,65 s), and speak while the agent speaks the cup. Button "Free Hands" (set by default), Space always works. ⚠️ Mohamed Amine : It touches your Voice page (useVoiceSession : readRms, stopTalking({(quiet})), reread.
  - ** Robust listening (free hands)**: no more lost pieces (the sentences said before the answer are combined into one
    single message, even if cut in full transcription), multiple voices separated by Soniox ([caller] / [other voice])
    and dubious words marked "word(?)" → the agent ignores the other voices, keeps the last correction, asks again a word
    - Checked in real life. (2 Votes ElevenLabs → Soniox ; 3 the agent's answers). ⚠️ Mohamed Amine : key
    voice_session (Conversation.pending), utterance.py, Soniox.py (enable_speaker_diarization): relis stp.
- In progress: T4 (two brains + Jev).
- For Daycem: S05·2 waits `get_price` but `quote_line` (Amine K.) just answers → add `quote_line` to `tools_any`;
  S05·1 "82" is said in letters ("eighty-two") → add this form to `says_any`.
- Contract change: `caller` accepts `resume`; `caller_ready` returns `resume`. `TEAM_PRELOAD` no longer serves
  only to the automatic identification in the conversation (without form).
- I need: **Everyone → test the Voice page via "Who calls?"** (required before speaking).
- Switch(s): TEAM_PRELOAD = on · TEAM_PRODUCT_INSIGHT = on (after `make restart`) · TEAM_ORCHESTRATOR = off
- To test S40 / demo: `--reset` erases demo promo → restart `scripts/setup_demo_data.py` after.
