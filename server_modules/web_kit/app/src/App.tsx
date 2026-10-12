import { Router } from "@/lib/router";
import { SessionProvider } from "@/lib/session";

// Every file in src/pages is a screen: `src/pages/<file>.tsx` for the route that `src/routes.ts` gives that file.
const modules = import.meta.glob("./pages/**/*.{tsx,jsx}", { eager: true }) as Record<string, { default?: React.ComponentType }>;
const pages = Object.fromEntries(
  Object.entries(modules).map(([file, module]) => [file.replace(/^\.\/pages\//, "").replace(/\.(tsx|jsx)$/, ""), module]),
);

export default function App() {
  return (
    <SessionProvider>
      <Router pages={pages} />
    </SessionProvider>
  );
}
