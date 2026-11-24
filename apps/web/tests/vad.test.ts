/**
 * Team 12 (Youssef) · hands-free speech detection. Run: pnpm --filter @kit/web test
 * Each case feeds a level sample every 30 ms, like the page does.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { Vad } from "../src/features/assistant/vad";

/** Feed `ms` of a constant level; return the events with their time. */
function play(vad: Vad, segments: Array<[level: number, ms: number, agent?: boolean]>) {
  const events: Array<[string, number]> = [];
  let t = 0;
  for (const [level, ms, agent] of segments) {
    for (let end = t + ms; t < end; t += 30) {
      const ev = vad.feed(level, t, agent ?? false);
      if (ev) events.push([ev, t]);
    }
  }
  return events;
}

test("a sentence then a pause: start soon after the voice, end after ~650 ms of quiet", () => {
  const ev = play(new Vad(), [[0.004, 600], [0.12, 1500], [0.004, 1000]]);
  assert.deepEqual(ev.map((e) => e[0]), ["start", "end"]);
  assert.ok(ev[0][1] - 600 <= 150, `start late: ${ev[0][1]}`);
  assert.ok(ev[1][1] - 2100 >= 600 && ev[1][1] - 2100 <= 720, `end at ${ev[1][1]}`);
});

test("a short hesitation inside the sentence (« euh… » 400 ms) does not end it", () => {
  const ev = play(new Vad(), [[0.004, 300], [0.1, 800], [0.006, 400], [0.1, 800], [0.004, 900]]);
  assert.deepEqual(ev.map((e) => e[0]), ["start", "end"]);
});

test("a cough or a click (120 ms) is not an utterance", () => {
  const ev = play(new Vad(), [[0.004, 300], [0.2, 120], [0.004, 900]]);
  assert.deepEqual(ev.map((e) => e[0]), ["start", "cancel"]);
});

test("steady room noise never starts, even when louder than the minimum", () => {
  const vad = new Vad();
  const ev = play(vad, [[0.015, 5000]]);
  assert.deepEqual(ev, []);
});

test("the agent's own echo while it speaks does not interrupt it", () => {
  // echo = moderate level while the agent is audible
  const ev = play(new Vad(), [[0.004, 300], [0.045, 2000, true]]);
  assert.deepEqual(ev, []);
});

test("the caller talking over the agent (barge-in) does interrupt it", () => {
  const ev = play(new Vad(), [[0.004, 300], [0.2, 600, true]]);
  assert.equal(ev[0]?.[0], "start");
  assert.ok(ev[0][1] - 300 >= 200, "barge-in must last longer than a normal start");
});
