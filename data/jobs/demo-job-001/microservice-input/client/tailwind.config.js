/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#050818",
        secondary: "white",
        accent: "#7DC4FF",
      },
    },
  },
  plugins: [],
};
