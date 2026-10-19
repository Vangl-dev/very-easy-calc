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
    <section className={`sheet-panel ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            {title ? (
              <h2 className="text-[17px] font-semibold text-ink-900">{title}</h2>
            ) : null}
            {description ? (
              <p className="mt-1 text-[13px] leading-relaxed text-ink-500">
                {description}
              </p>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      )}
      <div className={padded ? "px-6 py-5" : ""}>{children}</div>
    </section>
  );
}
