import type { ReactNode } from "react";

interface TooltipProps {
  text: string;
  label?: string;
  children?: ReactNode;
}

/** Dica contextual com foco/hover — sem lógica de cálculo. */
export function Tooltip({ text, label = "Informação", children }: TooltipProps) {
  return (
    <span className="tooltip-host">
      {children ?? (
        <button
          type="button"
          aria-label={label}
          className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-ink-300 bg-white text-[11px] font-semibold text-ink-600 transition hover:border-brand-400 hover:text-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
        >
          i
        </button>
      )}
      <span role="tooltip" className="tooltip-bubble">
        {text}
      </span>
    </span>
  );
}
