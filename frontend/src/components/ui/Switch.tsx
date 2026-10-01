interface SwitchProps {
  id: string;
  checked: boolean;
  onChange: (checado: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function Switch({
  id,
  checked,
  onChange,
  label,
  description,
  disabled,
}: SwitchProps) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-ink-200 bg-ink-50/50 px-3 py-3">
      <div className="min-w-0">
        <label
          htmlFor={id}
          className="block cursor-pointer text-sm font-medium text-ink-900"
        >
          {label}
        </label>
        {description ? (
          <p className="mt-0.5 text-xs leading-relaxed text-ink-500">{description}</p>
        ) : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:opacity-50 ${
          checked ? "bg-brand-600" : "bg-ink-300"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}
