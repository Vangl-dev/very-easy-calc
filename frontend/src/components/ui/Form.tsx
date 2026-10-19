import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { Tooltip } from "./Tooltip";

interface FieldShellProps {
  label: string;
  hint?: string;
  tooltip?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor?: string;
}

export function FieldShell({
  label,
  hint,
  tooltip,
  required,
  children,
  htmlFor,
}: FieldShellProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <label htmlFor={htmlFor} className="label-legal">
          {label}
          {required ? <span className="ml-0.5 text-brand-700">*</span> : null}
        </label>
        {tooltip ? <Tooltip text={tooltip} label={`Ajuda: ${label}`} /> : null}
      </div>
      {children}
      {hint ? <p className="text-xs text-ink-500">{hint}</p> : null}
    </div>
  );
}

const baseInput =
  "field-line";

export function Input({
  label,
  hint,
  tooltip,
  required,
  id,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  tooltip?: string;
}) {
  return (
    <FieldShell label={label} hint={hint} tooltip={tooltip} required={required} htmlFor={id}>
      <input
        id={id}
        required={required}
        className={`${baseInput} ${className}`}
        {...props}
      />
    </FieldShell>
  );
}

export function Select({
  label,
  hint,
  tooltip,
  required,
  id,
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  tooltip?: string;
}) {
  return (
    <FieldShell label={label} hint={hint} tooltip={tooltip} required={required} htmlFor={id}>
      <select
        id={id}
        required={required}
        className={`${baseInput} appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 20 20%22><path stroke=%22%237a7468%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 stroke-width=%221.5%22 d=%22m6 8 4 4 4-4%22/></svg>')] bg-[length:1.05rem] bg-[right_0.15rem_center] bg-no-repeat pr-8 ${className}`}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export function Textarea({
  label,
  hint,
  tooltip,
  required,
  id,
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: string;
  tooltip?: string;
}) {
  return (
    <FieldShell label={label} hint={hint} tooltip={tooltip} required={required} htmlFor={id}>
      <textarea
        id={id}
        required={required}
        className={`${baseInput} min-h-[96px] resize-y border border-edge bg-panel px-3 py-2 ${className}`}
        {...props}
      />
    </FieldShell>
  );
}
