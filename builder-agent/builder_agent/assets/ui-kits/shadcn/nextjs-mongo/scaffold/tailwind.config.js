/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./app/**/*.{js,jsx}', './components/**/*.{js,jsx}', './lib/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        background: 'var(--background)', foreground: 'var(--foreground)',
        card: 'var(--surface)', border: 'var(--border)', muted: 'var(--surface-alt)',
        primary: 'var(--primary)', 'primary-foreground': 'var(--on-primary)',
      },
      borderRadius: { xl: 'var(--radius)' },
      fontFamily: { sans: ['var(--font-body)'], display: ['var(--font-heading)'] },
    },
  },
  plugins: [],
};
