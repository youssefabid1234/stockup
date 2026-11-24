# Mohamed Amine – "Never white"

## State of the branch

The voice yard is located on `mohamed-amine/voice-latency`. `TEAM_FILLERS=1` activates the changes for the tests. The next step is the comparison to the microphone on the pack of the Fournil. [Tasksheet](../tasks/mohamed-amine.md) · [Decisions and results](../../../DECISIONS.md)

| Step | Work on the industry | Remaining validation |
|---|---|---|
| T0 · Reference | Protocol below. The local kit runs with data and demonstration providers. | Raise S01 and S06 to the microphone on the crew station. |
| T1 · Phrases ready | At the opening of the connection, two sentences are synthesized in the background with the configured voice and stored. The first turn can start during the preparation. An empty synthesis can be re-opened. The bank test is active. | Listen to the voice of the team on the first call. |
| T2 · Time to talk | An explicit request for stock, price or order can trigger an already ready sentence. In-call additions and requests such as "I want 10 kg of flour" are also recognized. An effective ERP search can trigger the sentence if the formulation has escaped detection. Simple thanks and greetings remain silent until the answer. | Validate distribution with Youssef. Measure departure in less than 300 ms and first sound perceived in less than 1 s on S01/S05. |
| T3 · Keyboard | A long search can play some spaced keyboard gusts and a single recovery of the quantity and product if the request is clear. The agent's response or an interruption cancels the remaining sounds to play. The S10 test interrupts an ongoing search. The segment also closes if the turn fails. | Check the level and stop in the ear during S10. |
| T4 · Doubles | The reader discards repeated ads at the front of the answer, including "A moment, I'm checking" when an ad has already played. | With Daycem, validate the tone and set set below. |
| T5 · First useful sentence | The preparation uses the shared HTTP connection from the supplier. A rather long first proposal can start at comma. The measurement of the first byte of the synthesis remains distinct from the first sound of the turn. | Check the prosody and aim for `ttsFirstByteMs < 300` in the first round. |
| T6 · Transcript | The jargon and the first names ERP take precedence in the vocabulary transmitted to the voice recognition. The basic jargon remains available if the ERP does not respond. | Dicter "Ten de tradi", "laminating butter", "strong flour", "T55" and a first name of the pack at Soniox. |
| T7 · Automatic end of speech (optional) | Decision to keep Space for demo. | Re-examine automatic detection after micro tests. |

## Decisions to share

- **Youssef.** The current orchestrator delegates to the agent ERP. `TEAM_FILLERS` controls the greeting and announcements, regardless of the state of `TEAM_ORCHESTRATOR`. The final answer interrupts the wait. [Contrat between the yards](../interfaces.md)
- **Daycem.** Proposal for voice rules when `TEAM_FILLERS=1` and the voice layer manages the wait: "Give the result of your check directly. The voice player is responsible for making the client wait."

## Microbial test

1. Load the Fournil pack locally and open the Voice page with the team's suppliers. With the switches off, play S01 and S06. Pick up by turn `sttMs`, `llmFirstTokenMs`, `ttsFirstByteMs`, `totalMs` and `perceivedMs`. Write down the suppliers and distinguish the first round from the next.
2. Activate `TEAM_FILLERS=1`, restart AI and replay S01, S05 and S06 under the same conditions. Take a look at what sound comes first and when the helpful answer begins. Media report and worst case in [DECISIONS.md](../../../DECISIONS.md).
3. On S10, resume Space **dependant** the first sound. Verify that the old turn is cut and that the new request is transcribed. On S11, say "That's all, thank you. Goodbye." and listen to the direct answer. The script replays the tricks one after the other. The integration test exercises the interruption and closure of the segment during an active turn. [S10](../../../scenarios/S10.json) · [S11](../../../scenarios/S11.json) · [Voice tests](../../../apps/ai/tests/test_voice_fillers.py)


## Natural telephone response

The template can send a few lines of text before calling the ERP. The reader received them immediately, which could make an internal note audible before greeting.

1. Wait for the final answer before sending it to the browser and synthesis. The ads and keyboard of the voice service can always play during the search.
2. Filter explicit analysis blocks and recognizable reasoning primers. Keep ERP calls, their results and the answer heard in history.
3. Give the vocal model instructions of spoken French with examples. Naturally greet at the opening, give the useful result, ask one question at a time and keep the reasoning silent.
4. Test one note before calling ERP and another before "Hello" in the final answer. Check the displayed text, the words transmitted to the synthesis and the history after an interruption.

Synthesis of the useful response begins after the end of the model generation. Comparison with the micro will have to check the effect on the delay until this response.

## Variant with fast model

With `TEAM_FILLERS=2`, "I'm going to see" opens the wait. The quick model selects a short passage from the transcript in parallel with Agent ERP. The resume uses the client's words. A short and ambiguous request is taken up in full to keep the options and denials. A long request that could change the meaning receives "One moment, I check". In all three modes, only the final answer of Agent ERP is read. The resumption in preparation is cancelled if the answer arrives or if the client resumes the word.

To compare, keep the same suppliers and the same value of `TEAM_ORCHESTRATOR`. Re-launch the AI between `TEAM_FILLERS=1` and `TEAM_FILLERS=2`. Test "Ten kilos of flour or two bags?" during a fairly long check, then "Thank you" to verify the direct response. 2 mode uses the same supplier's `TEAM_FAST_MODEL` model as the main agent, without additional ERP call.


## Greeting from the first round

The form "Who calls?" offers optional civility. With the modes `1`, `2` and `3`, the audio "Hello Madam", "Hello Sir" or "Hello" is prepared during the loading of the plug. The first release of the microphone triggers this greeting from the cache during the finalisation of the transcription. For a stock or order request, the announcement of the selected mode can follow. A reconnection does not replay the greeting already broadcast.

To compare `0`, `1`, `2` and `3`, start a new call after each restart of the AI, choose the same civility and play the same request. Watch "Perceived" after the release. Tests check that the greeting is sent before the final transcription. The 0,5 s lens remains to be measured in the browser.


## Combined mode

`TEAM_FILLERS=3` uses the 1 mode ads, plays a short keyboard gust if the search lasts and prepares the 2 mode to resume in parallel. If no faithful short recovery is available, the player uses the neutral restart. The sounds that remain in preparation are cancelled upon arrival of the answer or if the client resumes the speech. Thanks and greetings only keep a direct answer.
