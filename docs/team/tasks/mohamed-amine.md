# Mohamed Amine – "Never white" (speed + voice)

**Journal Criteria** : Fast (end of speech → first sound < 1,5 s) and Natural.
**Interruptor**: `TEAM_FILLERS`. **Branche**: `mohamed-amine/<sujet>` (e.g. `mohamed-amine/fillers`).

## Real Life
Nadine asks "do you still have AOP laminating butter?" Lucie answers ** right away** "I'm looking at this...", we hear her
then she gives the answer, never three seconds of silence on the phone.
Today the agent puts **≈ 4 s before his first word** ( measured on S03 : 4,1 (s) and **≈ 9 s** in total in vocal.

## Your files
| File | Role |
|---|---|
| `apps/ai/app/services/fillers.py` | **to you**: bank of waiting sentences, keyboard noise, decisions |
| `apps/ai/app/services/voice_session.py` | **to you** (kit file): `Speaker.play_audio`, hot TTS connection; `fillers.on_turn_start` / `on_tool_call` call points are already connected |
| `apps/ai/app/services/vocabulary.py` | **to you** (kit file): vocabulary sent to transcription |
| `apps/ai/app/assets/` | **to you**: keyboard sound (short, free of rights or generated mp3) |
| `apps/ai/app/clients/elevenlabs.py`, `soniox.py` | read only, except for specific reason (FAQ: "already set") |

First read: `GUIDE-VOIX.md` §1 (one tower anatomy), §3 (kit measurements), §4.7 (girls), §4.8-4.9 (TTS), §5
(natural), §8 (plan 24 h); [interfaces.md](../interfaces.md) §1.

## Your tasks, in order
| # | Task | No more when |
|---|---|---|
| T0 | Kit launched on your PC; Voice page: play S01 and S06 aloud; rate `sttMs`, `llmFirstTokenMs`, `ttsFirstByteMs`, `totalMs`, `perceivedMs` (line "original kit" of DECISIONS.md) | the line is filled |
| T1 | `Speaker.play_audio(mime, data)` in voice_session.py + `FillerBank.warm_up(tts)` (synthetize each ** sentence once** at session opening, with the voice of the team) | `test_filler_bank_warms_up_every_phrase` (remove skip) passes |
| T2 | `on_turn_start`: Play a waiting sentence **< 300 ms** after release, **only** if the turn will call tools (anti-scaling rule, §1 interfaces, to decide with Youssef) | perceived < 1 s on S01/S05, no waiting phrase on "thank you" |
| T3 | `on_tool_call`: keyboard noise during ERP searches, cut as soon as the real answer starts | listening: natural, not sound over voice |
| T4 | Avoid duplicates: when `TEAM_FILLERS=1`, the agent should no longer say "I look." (VOICE_RULES allows it) → propose to Daycem the sentence to be added in its rules | more double "I look" |
| T5 | TTS: Hot-maintained connection (GUIDE-VOIX §4.9), first sentence cut earlier (§4.8) | `ttsFirstByteMs` < 300 ms from the 1er round |
| T6 | Vocabulary STT: add jargon ("tradi", "laminating butter", "chocolatine", "strong flour", "T55" ...) and contact names in `vocabulary.py` | dictated aloud, "ten of tradi" is well transcribed |
| T7 | (if time) VAD / automatic speech end (§4.2), keeping Space for demo | decision noted in DECISIONS.md |

**Tes scenarios** (S10–S19, at least 2): e.g. a client who shuts off the agent (barge-in), and a
very short question ("that's all, thank you") that must not trigger any waiting phrase.

## Who to coordinate with
- **Youssef**: who speaks first (waiting phrase or fast agent) → interfaces §1, to H+2.
- **Daycem**: The tone of the waiting phrases and the instructions that prevent the agent from saying "I look" himself.

## Traps
- A waiting sentence on a tower that would have responded in 600 ms **ralentit** the agent: measurement before/after.
- The waiting phrases do not contain **jamais** of number or promise.
- After each change: replay S01, S05, S06 (`--voice` for real times) and record the numbers.

## The first message to give to your AI code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md and docs/team/tasks/mohamed-amine.md. I am Mohamed
> Amine. Explain to me T0 and T1 in simple words, propose a plan, and wait for Mon chord before encode.
> My files.
