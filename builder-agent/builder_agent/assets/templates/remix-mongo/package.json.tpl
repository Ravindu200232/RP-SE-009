{
  "name": "sketch-remix",
  "private": true,
  "type": "module",
  "sideEffects": false,
  "scripts": {
    "dev": "remix vite:dev",
    "build": "remix vite:build",
    "start": "remix-serve ./build/server/index.js",
    "seed": "node scripts/seed.mjs",
    "test": "vitest run"
  },
  "dependencies": {
    "@remix-run/node": "^2.17.5",
    "@remix-run/react": "^2.17.5",
    "@remix-run/serve": "^2.17.5",
    "isbot": "^5.2.2",
    "mongoose": "^8.9.5",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@remix-run/dev": "^2.17.5",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@vitejs/plugin-react": "^4.7.0",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.1",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.19",
    "vite": "^6.0.11",
    "vitest": "^3.2.7"
  },
  "engines": {
    "node": ">=20.0.0"
  }
}
