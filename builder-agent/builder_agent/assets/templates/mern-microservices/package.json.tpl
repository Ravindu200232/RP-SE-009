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
    "test": "npm run test --workspaces --if-present"
  },
  "engines": {
    "node": ">=20"
  }
}
