/**
 * A transcript still being heard (streaming STT): the final words in the normal colour, the provisional ones —
 * which the STT may still change — muted italic. Once `final`, plain text.
 * `stable` is the leading part of `text` made of final words (server: transcript.stable).
 */
export function LiveTranscript({ text, stable = "", final }: { text: string; stable?: string; final?: boolean }) {
  if (final) return <>{text}</>;
  const cut = text.startsWith(stable) ? stable.length : 0;
  return (
    <span>
      {text.slice(0, cut)}
      <span className="italic text-muted-foreground">{text.slice(cut)}</span>
    </span>
  );
}
