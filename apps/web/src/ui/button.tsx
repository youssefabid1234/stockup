import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "default" | "primary" | "ghost" | "danger";
export type ButtonSize = "md" | "sm";

export function buttonClass({ variant = "default", size = "md", iconOnly = false }: { variant?: ButtonVariant; size?: ButtonSize; iconOnly?: boolean } = {}) {
  return cn(
    "inline-flex shrink-0 select-none items-center justify-center gap-1.5 whitespace-nowrap rounded-[4px] border font-medium transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 disabled:pointer-events-none disabled:opacity-50",
    size === "md" ? "h-8 text-[13px]" : "h-[26px] text-[12px]",
    iconOnly ? (size === "md" ? "w-8" : "w-[26px]") : size === "md" ? "px-3" : "px-2",
    variant === "default" && "border-border bg-card text-foreground hover:border-border-hover hover:bg-muted",
    variant === "primary" && "border-primary bg-primary text-primary-foreground hover:border-primary-hover hover:bg-primary-hover",
    variant === "ghost" && "border-transparent bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
    variant === "danger" && "border-border bg-card text-destructive hover:border-destructive/40 hover:bg-destructive/10",
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  loading?: boolean;
  kbd?: string;
}

/** <Button variant="primary" icon={Check} onClick=…>Confirmer</Button> */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "default", size = "md", icon: Icon, iconRight: IconRight, loading, kbd, className, children, disabled, type = "button", ...rest },
  ref,
) {
  const s = size === "md" ? 14 : 13;
  return (
    <button ref={ref} type={type} disabled={disabled || loading} className={cn(buttonClass({ variant, size }), className)} {...rest}>
      {loading ? <Spinner size={s} /> : Icon ? <Icon size={s} strokeWidth={1.75} aria-hidden /> : null}
      {children}
      {IconRight ? <IconRight size={s} strokeWidth={1.75} aria-hidden /> : null}
      {kbd ? <Kbd className="ml-1">{kbd}</Kbd> : null}
    </button>
  );
});

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  label: string; // aria-label + tooltip
  variant?: ButtonVariant;
  size?: ButtonSize;
  active?: boolean;
}

/** <IconButton icon={X} label="Fermer" onClick=… /> (ghost by default) */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icon, label, variant = "ghost", size = "md", active, className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={active}
      className={cn(buttonClass({ variant, size, iconOnly: true }), active && "bg-row-selected text-foreground hover:bg-row-selected", className)}
      {...rest}
    >
      <Icon size={size === "md" ? 15 : 13} strokeWidth={1.75} aria-hidden />
    </button>
  );
});

export function Spinner({ size = 14, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" className={cn("animate-spin", className)} aria-hidden>
      <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="2" />
      <path d="M14.5 8A6.5 6.5 0 0 0 8 1.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd className={cn("inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[3px] border border-border bg-muted px-1 font-sans text-[10.5px] font-medium text-muted-foreground", className)}>
      {children}
    </kbd>
  );
}
