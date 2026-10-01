import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { BasesPage } from "./pages/BasesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { MeusCalculosPage } from "./pages/MeusCalculosPage";
import { NovoCalculoPage } from "./pages/NovoCalculoPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="novo-calculo" element={<NovoCalculoPage />} />
        <Route path="meus-calculos" element={<MeusCalculosPage />} />
        <Route path="bases" element={<BasesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
