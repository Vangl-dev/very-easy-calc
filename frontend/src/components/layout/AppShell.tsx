import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { api } from "../../lib/api";
import { Header } from "./Header";
import { Layout } from "./Layout";

export function AppShell() {
  const [appVersion, setAppVersion] = useState<string | undefined>(undefined);

  useEffect(() => {
    let ativo = true;
    api
      .health()
      .then((saude) => {
        if (ativo) setAppVersion(saude.version);
      })
      .catch(() => {
        if (ativo) setAppVersion(undefined);
      });
    return () => {
      ativo = false;
    };
  }, []);

  return (
    <>
      <Header appVersion={appVersion} />
      <Layout>
        <Outlet />
      </Layout>
    </>
  );
}
