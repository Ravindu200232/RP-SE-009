import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Light "workbench" palette
        bg: {
          DEFAULT: '#ffffff',
          soft: '#f6f7f9',
          panel: '#eef0f4',
          elevated: '#e6e9ef',
        },
        border: {
          DEFAULT: '#e2e5ea',
          soft: '#eef0f3',
        },
        accent: {
          DEFAULT: '#7c5cff',
          soft: '#6a4bf2',
          muted: '#ece8ff',
        },
        text: {
          DEFAULT: '#14161c',
          muted: '#586072',
          faint: '#8a92a3',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        loading: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(400%)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
        blink: 'blink 1s step-start infinite',
        loading: 'loading 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
