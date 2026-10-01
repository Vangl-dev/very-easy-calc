import { NavLink } from "react-router-dom";

export interface NavItem {
  to: string;
  label: string;
  description?: string;
}

const itens: NavItem[] = [
  {
    to: "/novo-calculo",
    label: "Novo cálculo",
    description: "Cível, alimentos ou atualização monetária",
  },
  {
    to: "/meus-calculos",
    label: "Meus cálculos",
    description: "Lista e memória dos cálculos salvos",
  },
  {
    to: "/bases",
    label: "Bases / Indexadores",
    description: "Versões, cobertura e cadastros manuais",
  },
];

export function Navigation({ compact = false }: { compact?: boolean }) {
  return (
    <nav
      aria-label="Navegação principal"
      className={compact ? "flex flex-wrap gap-2" : "flex flex-col gap-1"}
    >
      {itens.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            [
              "rounded-xl border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600",
              compact
                ? "px-3 py-2 text-sm"
                : "px-3 py-2.5 text-sm",
              isActive
                ? "border-brand-200 bg-brand-50 text-brand-800"
                : "border-transparent text-ink-700 hover:border-ink-200 hover:bg-white hover:text-ink-900",
            ].join(" ")
          }
        >
          <span className="font-medium">{item.label}</span>
          {item.description && !compact ? (
            <span className="mt-0.5 block text-xs text-ink-500">{item.description}</span>
          ) : null}
        </NavLink>
      ))}
    </nav>
  );
}

export function NavigationCompact() {
  return <Navigation compact />;
}
