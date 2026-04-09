```jsx
import { Routes, Route } from "react-router-dom";
import Sidebar from "./Sidebar";
import Dashboard from "./Dashboard";

function DashboardPage() {
  return (
    <>
      <Sidebar />
      <main className="flex-1 p-4 bg-gray-100 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </main>
    </>
  );
}

export default DashboardPage;
```