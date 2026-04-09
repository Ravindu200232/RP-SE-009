/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/app/**/*.{js,jsx,ts,tsx}',
    './src/components/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        cosmic: {
          950: '#03030F',
          900: '#06061A',
          800: '#0A0A28',
          700: '#0F0F3D',
        },
        neon: {
          purple: '#7C3AED',
          blue:   '#2563EB',
          cyan:   '#06B6D4',
          gold:   '#F59E0B',
          green:  '#10B981',
          pink:   '#EC4899',
        }
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'float':    'float 6s ease-in-out infinite',
        'slide-up': 'slideUp 0.4s ease-out',
        'fade-in':  'fadeIn 0.3s ease-out',
        'spin-slow':'spin 3s linear infinite',
      },
      keyframes: {
        float:   { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-10px)' } },
        slideUp: { from: { opacity: 0, transform: 'translateY(20px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
      },
    }
  },
  plugins: [],
};
