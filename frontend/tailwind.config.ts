import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#f0f4f9",
        foreground: "#111827",
        canvas: "#faf6f0",
        brand: {
          darkred: "#580707",
          crimson: "#7b0d0d",
          burnt: "#c63205",
          orange: "#e64e0d",
          amber: "#f26b1d",
          peach: "#fcefe6",
        },
      },
      borderRadius: {
        "2xl": "18px",
        "3xl": "24px",
        "4xl": "32px",
      },
      fontFamily: {
        sans: ["var(--font-clash)", "var(--font-jakarta)", "'Plus Jakarta Sans'", "system-ui", "-apple-system", "sans-serif"],
        display: ["var(--font-clash)", "var(--font-jakarta)", "'Plus Jakarta Sans'", "system-ui", "-apple-system", "sans-serif"],
        clash: ["var(--font-clash)", "'Clash Display'", "system-ui", "-apple-system", "sans-serif"],
        jakarta: ["var(--font-jakarta)", "'Plus Jakarta Sans'", "system-ui", "-apple-system", "sans-serif"],
        dotted: ["var(--font-doto)", "'Doto'", "monospace"],
        numbers: ["var(--font-doto)", "'Doto'", "monospace"],
      },
      boxShadow: {
        card: "0 2px 12px -2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.02)",
        "card-hover": "0 8px 24px -4px rgba(0, 0, 0, 0.07), 0 2px 6px rgba(0, 0, 0, 0.03)",
        glass: "0 20px 40px -15px rgba(0, 0, 0, 0.2)",
        popover: "0 12px 32px -8px rgba(0, 0, 0, 0.24)",
      },
    },
  },
  plugins: [],
};
export default config;