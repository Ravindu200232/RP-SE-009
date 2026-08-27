export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: '#6366f1',
        accent2: '#22d3ee',
        dark: '#0a0a0f',
        dark2: '#12121a',
        card: '#1e1e2e',
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
