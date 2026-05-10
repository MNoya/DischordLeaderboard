import type { Config } from "tailwindcss";

// Theme tokens from src/theme.ts ported to Tailwind. Surfaces, accents, and
// fonts are exposed as utility classes (e.g. `bg-bg`, `text-muted`,
// `font-display`) so component code reads as "background = bg" instead of
// "background = #0a0c10".
//
// Where shadcn primitives expect HSL CSS vars (--primary, etc.), we mirror the
// values into vars so future shadcn components Just Work.

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0c10",
        surface: "#14181f",
        surface2: "#1d2330",
        border: "#2a3142",
        border2: "#3b4458",
        text: "#e6ecf5",
        subtle: "#b8c0d0",
        muted: "#7a8395",
        dim: "#4a5163",

        green: {
          DEFAULT: "#2ee85c",
          2: "#1fd14c",
        },
        teal: "#22d4c0",
        gold: "#ffc63a",
        red: "#ff5e5e",
      },
      fontFamily: {
        display: ["'Bebas Neue'", "sans-serif"],
        body: ["'Space Grotesk'", "Inter", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      fontVariantNumeric: {
        tabular: ["tabular-nums"],
      },
      keyframes: {
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
      },
      animation: {
        pulse: "pulse 1.4s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
