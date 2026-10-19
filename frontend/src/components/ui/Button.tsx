import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variante = "primary" | "secondary" | "ghost" | "outline";
type Tamanho = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variante;
  size?: Tamanho;
  children: ReactNode;
}

const variantes: Record<Variante, string> = {
  primary:
    "border border-brand-700 bg-brand-700 text-white hover:bg-brand-800 hover:border-brand-800 focus-visible:outline-brand-700",
  secondary:
    "border border-edge bg-panel text-ink-700 hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-ink-500",
  outline:
    "border border-ink-300 bg-panel text-ink-800 hover:bg-ink-50 focus-visible:outline-brand-700",
  ghost:
    "border border-transparent bg-transparent text-ink-500 hover:text-brand-700 hover:bg-brand-50 focus-visible:outline-ink-500",
};

const tamanhos: Record<Tamanho, string> = {
  sm: "h-8 px-3 text-[11px] font-semibold uppercase tracking-legal",
  md: "h-10 px-4 text-[12px] font-semibold uppercase tracking-legal",
  lg: "h-11 px-6 text-[12px] font-semibold uppercase tracking-legalWide",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variantes[variant]} ${tamanhos[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
