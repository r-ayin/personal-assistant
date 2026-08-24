import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0E1116",
        "bg-elev": "#161A22",
        "bg-elev-2": "#1C2230",
        border: "#262D3B",
        "border-soft": "#1F2533",
        text: "#E6EAF2",
        "text-dim": "#94A0B4",
        "text-mute": "#5B6577",
        indigo: "#5B8DEF",
        green: "#3FB68B",
        gold: "#E0A458",
        red: "#E0584F",
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Source Han Sans CN"', '"Noto Sans CJK SC"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
