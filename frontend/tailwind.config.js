/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9ebff",
          200: "#bcdeff",
          300: "#8ec9ff",
          400: "#59a9ff",
          500: "#3388fc",
          600: "#1f66f1",
          700: "#1850de",
          800: "#1a43b4",
          900: "#1b3b8e",
          950: "#152657",
        },
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5dae3",
          300: "#b0bac9",
          400: "#8594ad",
          500: "#667795",
          600: "#515f7a",
          700: "#434e64",
          800: "#3a4354",
          900: "#343a47",
          950: "#22262f",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(21, 38, 87, 0.06), 0 8px 24px rgba(21, 38, 87, 0.06)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
