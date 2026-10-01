import type { ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
        {children}
      </main>
      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-4 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            Very Easy Calc — o sistema executa os parâmetros definidos pelo usuário;
            não decide interpretação jurídica.
          </p>
          <p>Backend FastAPI · memória de cálculo · PDF/XLSX</p>
        </div>
      </footer>
    </div>
  );
}
