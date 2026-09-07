{
  "name": "sketch-next",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev -p 3200",
    "build": "next build",
    "start": "next start -p 3200",
    "seed": "node scripts/seed.mjs",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "^15.1.4",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "mongoose": "^8.9.5"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@vitejs/plugin-react": "^4.3.4",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8"
  }
}
