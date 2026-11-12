import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#070a0f", 900: "#0b1017", 850: "#0e141d", 800: "#121a24", 700: "#1a2431", 600: "#243040" },
        brand: { 300: "#a5b4fc", 400: "#818cf8", 500: "#6366f1", 600: "#4f46e5" },
        accent: { 400: "#22d3ee", 500: "#06b6d4" },
      },
      fontFamily: {
        sans: ["Vazirmatn", "IRANSans", "Tahoma", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(99,102,241,.25), 0 8px 40px -12px rgba(79,70,229,.45)",
      },
      animation: { "pulse-slow": "pulse 2.5s cubic-bezier(0.4,0,0.6,1) infinite" },
    },
  },
  plugins: [],
};
export default config;
