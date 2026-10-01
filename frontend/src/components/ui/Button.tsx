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
    "bg-brand-600 text-white hover:bg-brand-700 focus-visible:outline-brand-600 shadow-sm",
  secondary:
    "bg-ink-100 text-ink-800 hover:bg-ink-200 focus-visible:outline-ink-500",
  outline:
    "border border-ink-300 bg-white text-ink-800 hover:bg-ink-50 focus-visible:outline-brand-600",
  ghost: "text-ink-700 hover:bg-ink-100 focus-visible:outline-ink-500",
};

const tamanhos: Record<Tamanho, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-3.5 py-2 text-sm",
  lg: "px-4 py-2.5 text-sm",
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
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variantes[variant]} ${tamanhos[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
