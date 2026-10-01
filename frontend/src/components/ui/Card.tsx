import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}

export function Card({
  title,
  description,
  action,
  children,
  className = "",
  padded = true,
}: CardProps) {
  return (
    <section
      className={`rounded-2xl border border-ink-200/80 bg-white shadow-card ${className}`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-ink-100 px-5 py-4">
          <div className="min-w-0">
            {title ? (
              <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
            ) : null}
            {description ? (
              <p className="mt-1 text-xs leading-relaxed text-ink-500">{description}</p>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
