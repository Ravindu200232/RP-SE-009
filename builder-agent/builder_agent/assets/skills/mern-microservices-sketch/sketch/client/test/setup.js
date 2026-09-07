// The runner-specific entry. Importing '@testing-library/jest-dom' instead
// requires a global `expect`, which is exactly the mismatch that makes a
// client suite collect zero tests.
import '@testing-library/jest-dom/vitest';
