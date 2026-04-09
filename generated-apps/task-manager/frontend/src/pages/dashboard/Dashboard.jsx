'use client';
```jsx
import React, { useEffect } from "react";
import TaskList from "./TaskList";
import AnalyticsChart from "./AnalyticsChart";

function Dashboard() {
  const [token] = useState(localStorage.getItem("token"));

  if (!token) window.location.href = "/login";

  return (
    <main className="flex h-screen overflow-hidden">
      <aside className="fixed md:static z-40 top-0 left-0 h-full w-64 bg-white shadow-md transform transition-transform">
        <div className="p-4 font-bold text-lg border-b">Dashboard</div>
        <nav>...</nav>
        <button onClick={() => { localStorage.clear(); window.location.href = "/login" }}>Logout</button>
      </aside>
      <section className="flex-1 p-4 bg-gray-100 overflow-y-auto">
        <TaskList />
        <AnalyticsChart />
      </section>
    </main>
  );
}

export default Dashboard;
```