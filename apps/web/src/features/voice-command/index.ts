/** Single-turn voice command (POST /ai/command): global hold-to-talk (⌥ Space), HUD, header button, shared engine. */
export { VoiceCommandProvider, VoiceCommandButton, VoiceCommandHud, RunBody, VOICE_COMMAND_HINT } from "./VoiceCommand";
export {
  useVoiceCommand, startCommand, stopCommand, sendCommandText, closeHud, openHud, setSpeak, stopSpeaking, clearCommandHistory,
  onCommandNavigate, type CommandRun, type CommandState, type CommandPhase,
} from "./engine";
export { LevelMeter, RunLinks, RunChips, MsChip, COMMAND_METRICS, metricValue, fmtMs, type MetricKey } from "./parts";
