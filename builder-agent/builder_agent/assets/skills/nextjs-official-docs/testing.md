---
title: Testing
description: Learn how to set up Next.js with four commonly used testing tools — Cypress, Playwright, Vitest, and Jest.
url: "https://nextjs.org/docs/app/guides/testing"
docs_index: /docs/llms.txt
version: 16.3.5
lastUpdated: 2026-02-03
prerequisites:
  - "Guides: /docs/app/guides"
---


> For an index of all Next.js documentation, see [/docs/llms.txt](/docs/llms.txt).
In React and Next.js, there are a few different types of tests you can write, each with its own purpose and use cases. This page provides an overview of types and commonly used tools you can use to test your application.

## Types of tests

* **Unit Testing** involves testing individual units (or blocks of code) in isolation. In React, a unit can be a single function, hook, or component.
* **Component Testing** is a more focused version of unit testing where the primary subject of the tests is React components. This may involve testing how components are rendered, their interaction with props, and their behavior in response to user events.
* **Integration Testing** involves testing how multiple units work together. This can be a combination of components, hooks, and functions.
* **End-to-End (E2E) Testing** involves testing user flows in an environment that simulates real user scenarios, like the browser. This means testing specific tasks (e.g. signup flow) in a production-like environment.
* **Snapshot Testing** involves capturing the rendered output of a component and saving it to a snapshot file. When tests run, the current rendered output of the component is compared against the saved snapshot. Changes in the snapshot are used to indicate unexpected changes in behavior.

## Async Server Components

Since `async` Server Components are new to the React ecosystem, some tools do not fully support them. In the meantime, we recommend using **End-to-End Testing** over **Unit Testing** for `async` components.

## Guides

See the guides below to learn how to set up Next.js with these commonly used testing tools:

- [Cypress](/docs/app/guides/testing/cypress)
  - Learn how to set up Cypress with Next.js for End-to-End (E2E) and Component Testing.
- [Jest](/docs/app/guides/testing/jest)
  - Learn how to set up Jest with Next.js for Unit Testing and Snapshot Testing.
- [Playwright](/docs/app/guides/testing/playwright)
  - Learn how to set up Playwright with Next.js for End-to-End (E2E) Testing.
- [Vitest](/docs/app/guides/testing/vitest)
  - Learn how to set up Vitest with Next.js for Unit Testing.

---

For a semantic overview of all documentation, see [/docs/sitemap.md](/docs/sitemap.md)

For an index of all available documentation, see [/docs/llms.txt](/docs/llms.txt)