import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--color-bg-primary)",
        surface: "var(--color-bg-surface)",
        foreground: "var(--color-text-primary)",
        primary: "var(--color-text-primary)",
        secondary: "var(--color-text-secondary)",
        border: "var(--color-border)",
        brand: {
          sage: "var(--color-brand-sage)",
        },
        accent: {
          light: "var(--color-accent-light)",
          gold: "var(--color-accent-gold)",
        },
        status: {
          success: "var(--color-success)",
          warning: "var(--color-warning)",
          error: "var(--color-error)",
          info: "var(--color-info)",
        }
      },
      fontFamily: {
        sans: ["var(--font-inter)"],
        serif: ["var(--font-source-serif)"],
        mono: ["var(--font-jetbrains-mono)"],
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        pill: "999px",
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
export default config;
