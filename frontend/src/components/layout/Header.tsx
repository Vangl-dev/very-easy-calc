import { Link } from "react-router-dom";
import { NavigationCompact } from "./Navigation";
import { Tooltip } from "../ui/Tooltip";

interface HeaderProps {
  appVersion?: string;
}

export function Header({ appVersion }: HeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-panel">
      <div className="mx-auto flex max-w-page flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="flex items-center gap-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
          >
            <span
              aria-hidden="true"
              className="flex h-9 w-9 items-center justify-center border border-edge font-serif text-lg text-brand-700"
            >
              §
            </span>
            <span>
              <span className="block font-serif text-[20px] leading-tight tracking-[0.04em] text-ink-950">
                Very Easy Calc
              </span>
              <span className="mt-0.5 block text-[12px] text-ink-500">
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
