import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8001";

  // Mesma origem para o navegador: /api/... é repassado ao backend pelo Vite.
  // Assim funciona em localhost e pelo IP da rede local, sem depender de CORS.
  const proxy = {
    "/api": {
      target: apiTarget,
      changeOrigin: true,
    },
  };

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy,
    },
    preview: {
      port: 4173,
      proxy,
    },
  };
});
