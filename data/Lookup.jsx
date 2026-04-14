export default {
    SUGGSTIONS: [
        'Build a full Task Manager with kanban board, priorities, deadlines and dark UI',
        'Create an E-commerce store with product listings, cart, and checkout pages',
        'Build a personal Finance Tracker with charts, budgets, and expense categories',
        'Create a Blog Platform with home, post list, post detail, and about pages',
        'Build a Recipe App with search, categories, favorites, and recipe detail pages',
        'Create a Fitness Tracker with workout logs, progress charts, and goals',
        'Build a Job Board with listings, filters, job detail, and apply form',
        'Create a Portfolio Website with hero, projects, skills, and contact pages',
        'Build a Movie Database app with search, details, watchlist, and ratings',
        'Create a Notes App with rich text, tags, search, and folder organization',
        'Build a Social Dashboard with feed, profile, stats, and messaging UI',
        'Create a Learning Platform with courses, lessons, progress tracking',
    ],

    DEFAULT_FILE: {
        // Entry point — always imports ./App.jsx explicitly
        '/index.js': {
            code: `import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './App.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);`
        },

        // Default placeholder — use .jsx so AI-generated App.jsx overrides it directly
        '/App.jsx': {
            code: `import React from 'react';

export default function App() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0a 0%, #111827 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{ textAlign: 'center', color: '#fff' }}>
        <div style={{ fontSize: 56, marginBottom: 16 }}>⚡</div>
        <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8, color: '#fff' }}>
          Generating your app...
        </h1>
        <p style={{ color: '#9ca3af', fontSize: 16 }}>
          AI is building your project. Preview will appear here shortly.
        </p>
      </div>
    </div>
  );
}`
        },

        '/App.css': {
            code: `*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }
#root { min-height: 100vh; }`
        },

        '/public/index.html': {
            code: `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>App Preview</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>`
        }
    },

    // Packages available in Sandpack preview
    DEPENDANCY: {
        "react":                "^18.2.0",
        "react-dom":            "^18.2.0",
        "react-router-dom":     "^6.20.0",
        "lucide-react":         "^0.363.0",
        "framer-motion":        "^10.18.0",
        "react-toastify":       "^10.0.0",
        "tailwind-merge":       "^2.4.0",
        "uuid":                 "^9.0.0",
        "react-beautiful-dnd":  "^13.1.1",
        "recharts":             "^2.10.3",
        "date-fns":             "^3.3.1",
    }
}
