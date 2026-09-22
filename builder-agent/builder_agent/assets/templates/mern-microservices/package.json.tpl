{
  "name": "sketch-mern",
  "private": true,
  "type": "module",
  "workspaces": [
    "packages/*",
    "client"
  ],
  "scripts": {
    "dev": "node scripts/dev-all.mjs",
    "build": "npm run build --workspace client",
    "start": "node packages/gateway/src/server.js",
    "seed": "node scripts/seed.mjs",
    "test": "vitest run --reporter=default --reporter=json --outputFile=test-report.json",
    "start:all": "node scripts/start-all.mjs"
  },
  "engines": {
    "node": ">=20"
  },
  "dependencies": {
    "bcryptjs": "^2.4.3",
    "jsonwebtoken": "^9.0.2"
  },
  "devDependencies": {
    "vitest": "^2.1.8"
  }
}
