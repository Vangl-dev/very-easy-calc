import type { ReactNode } from "react";

type Tom = "info" | "success" | "warning" | "danger" | "neutral";

interface MessageProps {
  tom?: Tom;
  title?: string;
  children?: ReactNode;
  className?: string;
}

const tons: Record<Tom, string> = {
  info: "border-brand-200 bg-brand-50 text-brand-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  danger: "border-rose-200 bg-rose-50 text-rose-900",
  neutral: "border-ink-200 bg-ink-50 text-ink-800",
};

export function Message({ tom = "info", title, children, className = "" }: MessageProps) {
  return (
    <div
      role="status"
      className={`rounded-xl border px-4 py-3 text-sm leading-relaxed ${tons[tom]} ${className}`}
    >
      {title ? <p className="font-semibold">{title}</p> : null}
      {children ? <div className={title ? "mt-1" : ""}>{children}</div> : null}
    </div>
  );
}
