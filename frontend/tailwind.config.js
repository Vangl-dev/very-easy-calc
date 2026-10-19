/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f7f0f1",
          100: "#f0e0e3",
          200: "#e2c4ca",
          300: "#cd9aa6",
          400: "#b46d7f",
          500: "#9a4d62",
          600: "#7f3550",
          700: "#6f263d",
          800: "#5a1e31",
          900: "#4a1929",
          950: "#2e0f19",
        },
        ink: {
          50: "#f6f5f2",
          100: "#ecebe6",
          200: "#ddd9d0",
          300: "#c4beb2",
          400: "#9a9488",
          500: "#7a7468",
          600: "#5c574e",
          700: "#46423b",
          800: "#34312c",
          900: "#252525",
          950: "#171716",
        },
        paper: "#f7f5f1",
        panel: "#fffdf9",
        line: "#e6e1d8",
        edge: "#d8d2c6",
      },
      boxShadow: {
        card: "none",
        sheet: "0 1px 0 rgba(37, 37, 37, 0.03)",
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
        serif: [
          "Georgia",
          '"Times New Roman"',
          "Times",
          "serif",
        ],
      },
      letterSpacing: {
        legal: "0.12em",
        legalWide: "0.16em",
      },
      maxWidth: {
        sheet: "920px",
        page: "1120px",
      },
    },
  },
  plugins: [],
};
