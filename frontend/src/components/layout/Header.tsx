import { Link } from "react-router-dom";
import { NavigationCompact } from "./Navigation";
import { Tooltip } from "../ui/Tooltip";

interface HeaderProps {
  appVersion?: string;
}

export function Header({ appVersion }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-ink-200/80 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:py-4">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-3 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-sm font-bold text-white shadow-sm">
              VE
            </span>
            <span>
              <span className="block text-base font-semibold leading-tight text-ink-950">
                Very Easy Calc
              </span>
              <span className="block text-xs text-ink-500">
                Cálculos judiciais com memória auditável
                {appVersion ? ` · v${appVersion}` : ""}
              </span>
            </span>
          </Link>
          <Tooltip text="O backend é a única fonte de cálculo. O frontend exibe e organiza resultados — não recalcula índices." />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <NavigationCompact />
        </div>
      </div>
    </header>
  );
}
