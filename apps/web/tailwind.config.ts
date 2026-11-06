import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102a43",
        mist: "#f0f4f8",
        lagoon: "#0c6b58",
        coral: "#c81e1e",
        sand: "#d9e2ec",
        slate: "#243b53",
      },
      fontFamily: {
        display: ["\"Fraunces\"", "Georgia", "serif"],
        sans: ["\"Source Sans 3\"", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        grid: "linear-gradient(to right, rgba(16,42,67,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(16,42,67,0.06) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "28px 28px",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%,100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        rise: "rise 0.6s ease-out both",
        pulseSoft: "pulseSoft 2.4s ease-in-out infinite",
        shimmer: "shimmer 2.2s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
