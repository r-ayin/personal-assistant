import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        porcelain: {
          0: "var(--porcelain-0)",
          1: "var(--porcelain-1)",
          2: "var(--porcelain-2)",
        },
        ink: {
          900: "var(--ink-900)",
          700: "var(--ink-700)",
          500: "var(--ink-500)",
          300: "var(--ink-300)",
        },
        cinnabar: "var(--cinnabar)",
        indigo: "var(--indigo)",
        mineral: "var(--mineral)",
        ochre: "var(--ochre)",
        "text-main": "var(--text-main)",
        "text-dim": "var(--text-dim)",
        "text-weak": "var(--text-weak)",
      },
      borderRadius: {
        "card": "var(--r-lg)",
        "btn": "var(--r-md)",
      },
      fontFamily: {
        sans: ["'Noto Sans SC'", "'PingFang SC'", "sans-serif"],
        serif: ["'Noto Serif SC'", "'Source Han Serif SC'", "'Songti SC'", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
