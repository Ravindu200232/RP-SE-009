```jsx
import React from "react";
import { Link } from "react-router-dom";

function Home() {
  return (
    <>
      <section className="hero">
        <div className="container mx-auto py-16 flex items-center justify-between">
          <h2 className="text-5xl font-bold text-gray-900">Welcome to Task Manager</h2>
          <Link to="/login" className="bg-yellow-500 text-gray-900 px-4 py-3 rounded-lg hover:bg-gray-900 hover:text-yellow-500 transition-all uppercase tracking-wide">
            Get Started
          </Link>
        </div>
      </section>
    </>
  );
}

export default Home;
```