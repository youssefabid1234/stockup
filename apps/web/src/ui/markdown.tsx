/**
 * Markdown — the one markdown renderer of the app (assistant answers, Contexte entries, docs).
 * react-markdown + GFM (tables, task lists, strikethrough, autolinks), styled with the design tokens.
 * Raw HTML in the source is NOT rendered (safe for model output). Internal links ("/clients/cli_0001") use the router.
 */
import { memo, useState, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";
import { Segmented, Textarea } from "./input";

const components: Components = {
  h1: ({ node: _n, ...p }) => <h3 className="mt-3 text-[14px] font-semibold text-foreground first:mt-0" {...p} />,
  h2: ({ node: _n, ...p }) => <h4 className="mt-3 text-[13px] font-semibold text-foreground first:mt-0" {...p} />,
  h3: ({ node: _n, ...p }) => <h5 className="mt-2.5 text-[13px] font-medium text-foreground first:mt-0" {...p} />,
  h4: ({ node: _n, ...p }) => <h6 className="mt-2 text-[10.5px] font-medium uppercase tracking-[.08em] text-muted-foreground first:mt-0" {...p} />,
  h5: ({ node: _n, ...p }) => <h6 className="mt-2 text-[10.5px] font-medium uppercase tracking-[.08em] text-muted-foreground first:mt-0" {...p} />,
  h6: ({ node: _n, ...p }) => <h6 className="mt-2 text-[10.5px] font-medium uppercase tracking-[.08em] text-muted-foreground first:mt-0" {...p} />,
  p: ({ node: _n, ...p }) => <p {...p} />,
  strong: ({ node: _n, ...p }) => <strong className="font-semibold text-foreground" {...p} />,
  em: ({ node: _n, ...p }) => <em className="italic" {...p} />,
  del: ({ node: _n, ...p }) => <del className="text-muted-foreground" {...p} />,
  ul: ({ node: _n, className, ...p }) => (
    <ul className={cn("ml-4 list-disc space-y-0.5 marker:text-muted-foreground/70", className?.includes("contains-task-list") && "ml-0 list-none")} {...p} />
  ),
  ol: ({ node: _n, ...p }) => <ol className="ml-4 list-decimal space-y-0.5 marker:text-muted-foreground" {...p} />,
  li: ({ node: _n, className, ...p }) => <li className={cn("pl-0.5 [&>ol]:mt-0.5 [&>ul]:mt-0.5", className?.includes("task-list-item") && "flex items-start gap-1.5")} {...p} />,
  input: ({ node: _n, ...p }) => <input {...p} disabled className="mt-[3px] size-3 accent-[hsl(var(--primary))]" />,
  blockquote: ({ node: _n, ...p }) => <blockquote className="border-l-2 border-border pl-3 text-muted-foreground" {...p} />,
  hr: () => <hr className="my-2 border-border" />,
  a: ({ node: _n, href = "", ...p }) =>
    href.startsWith("/") ? (
      <Link to={href} className="text-primary underline-offset-2 hover:underline" {...p} />
    ) : (
      <a href={href} target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline" {...p} />
    ),
  code: ({ node: _n, className, children, ...p }) =>
    /language-/.test(className ?? "") ? (
      <code className={cn("font-mono text-[11.5px]", className)} {...p}>{children}</code>
    ) : (
      <code className="rounded-[3px] bg-muted px-1 py-px font-mono text-[11.5px] text-foreground" {...p}>{children}</code>
    ),
  pre: ({ node: _n, ...p }) => <pre className="overflow-x-auto rounded-[4px] border border-border bg-muted/50 px-2.5 py-2 leading-[17px]" {...p} />,
  table: ({ node: _n, ...p }) => (
    <div className="overflow-x-auto rounded-[4px] border border-border">
      <table className="w-full text-[12px]" {...p} />
    </div>
  ),
  thead: ({ node: _n, ...p }) => <thead className="bg-muted/50 text-left text-muted-foreground" {...p} />,
  tr: ({ node: _n, ...p }) => <tr className="border-t border-border first:border-t-0" {...p} />,
  th: ({ node: _n, style, ...p }) => <th className="whitespace-nowrap px-2 py-1 font-medium" style={style} {...p} />,
  td: ({ node: _n, style, ...p }) => <td className="px-2 py-1 align-top tabular-nums" style={style} {...p} />,
  img: () => null, // no remote images in model / context output
};

type Props = { text: string; className?: string; size?: "sm" | "md" } & Omit<ComponentPropsWithoutRef<"div">, "children">;

export const Markdown = memo(function Markdown({ text, className, size = "md", ...rest }: Props) {
  return (
    <div
      className={cn(
        "min-w-0 space-y-1.5 break-words",
        size === "md" ? "text-[13px] leading-[19px]" : "text-[12px] leading-[17px]",
        className,
      )}
      {...rest}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
});

/**
 * MarkdownEditor — one box, two views: "Aperçu" (rendered) and "Markdown" (raw, editable). Toggle in the header;
 * double-click the preview to edit. `onCommit` fires on blur (autosave editors), `onChange` on every keystroke.
 */
export function MarkdownEditor({ label, hint, value, onChange, onCommit, placeholder, defaultMode = "preview", minRows = 6, maxRows = 18 }: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  onCommit?: () => void;
  placeholder?: string;
  defaultMode?: "preview" | "raw";
  minRows?: number;
  maxRows?: number;
}) {
  const [mode, setMode] = useState<"preview" | "raw">(value.trim() ? defaultMode : "raw");
  const rows = Math.min(maxRows, Math.max(minRows, value.split("\n").length + 1));
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium text-secondary-foreground">{label}</span>
        <Segmented
          value={mode}
          onChange={setMode}
          options={[{ id: "preview", label: "Aperçu" }, { id: "raw", label: "Markdown" }]}
          className="[&_button]:px-2 [&_button]:py-px [&_button]:text-[11.5px]"
        />
      </div>
      {mode === "raw" ? (
        <Textarea
          aria-label={label}
          autoFocus={!!value.trim()}
          rows={rows}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onCommit}
          className="font-mono text-[12px]"
        />
      ) : (
        <div
          role="button"
          tabIndex={0}
          title="Double-cliquer pour modifier"
          onDoubleClick={() => setMode("raw")}
          onKeyDown={(e) => e.key === "Enter" && setMode("raw")}
          className="min-h-[64px] cursor-text rounded-[4px] border border-input bg-muted/30 px-3 py-2.5 hover:border-border-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70"
        >
          {value.trim() ? <Markdown text={value} className="text-secondary-foreground" /> : <span className="text-[13px] text-muted-foreground">{placeholder ?? "Vide"}</span>}
        </div>
      )}
      {hint ? <span className="text-[11.5px] text-muted-foreground">{hint}</span> : null}
    </div>
  );
}
