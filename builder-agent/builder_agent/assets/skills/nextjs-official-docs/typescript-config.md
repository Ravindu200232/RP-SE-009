---
title: typescript
description: Configure how Next.js handles TypeScript errors during production builds and specify a custom tsconfig file.
url: "https://nextjs.org/docs/app/api-reference/config/next-config-js/typescript"
docs_index: /docs/llms.txt
version: 16.3.5
lastUpdated: 2026-03-18
prerequisites:
  - "Configuration: /docs/app/api-reference/config"
  - "next.config.js: /docs/app/api-reference/config/next-config-js"
---


> For an index of all Next.js documentation, see [/docs/llms.txt](/docs/llms.txt).
Configure TypeScript behavior with the `typescript` option in `next.config.js`:

```js filename="next.config.js"
module.exports = {
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: 'tsconfig.json',
  },
}
```

## Options

| Option              | Type      | Default           | Description                                                      |
| ------------------- | --------- | ----------------- | ---------------------------------------------------------------- |
| `ignoreBuildErrors` | `boolean` | `false`           | Allow production builds to complete even with TypeScript errors. |
| `tsconfigPath`      | `string`  | `'tsconfig.json'` | Path to a custom `tsconfig.json` file.                           |

## `ignoreBuildErrors`

Next.js fails your **production build** (`next build`) when TypeScript errors are present in your project.

If you'd like Next.js to dangerously produce production code even when your application has errors, you can disable the built-in type checking step.

Note that this completely skips the TypeScript type checking step. It does not run TypeScript and suppress errors, it bypasses the check entirely.

If disabled, be sure you are running type checks as part of your build or deploy process, otherwise this can be very dangerous.

```js filename="next.config.js"
module.exports = {
  typescript: {
    // !! WARN !!
    // Dangerously allow production builds to successfully complete even if
    // your project has type errors.
    // !! WARN !!
    ignoreBuildErrors: true,
  },
}
```

## `tsconfigPath`

Use a different TypeScript configuration file for builds or tooling:

```js filename="next.config.js"
module.exports = {
  typescript: {
    tsconfigPath: 'tsconfig.build.json',
  },
}
```

See the [TypeScript configuration](/docs/app/api-reference/config/typescript#custom-tsconfig-path) page for more details.
---

For a semantic overview of all documentation, see [/docs/sitemap.md](/docs/sitemap.md)

For an index of all available documentation, see [/docs/llms.txt](/docs/llms.txt)