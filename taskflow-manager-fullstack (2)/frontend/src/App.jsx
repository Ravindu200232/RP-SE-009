import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ToastContainer, toast } from 'react-toastify';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import KanbanBoard from './pages/KanbanBoard';
import TaskDetails from './pages/TaskDetails';
import About from './pages/About';

const TASKS_STORAGE_KEY = 'taskflow.tasks';
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function App() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks();
  }, []);

  const updateStoredTasks = (updater) => {
    setTasks((currentTasks) => {
      const nextTasks = typeof updater === 'function' ? updater(currentTasks) : updater;
      localStorage.setItem(TASKS_STORAGE_KEY, JSON.stringify(nextTasks));
      return nextTasks;
    });
  };

  const requestJson = async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.success) {
      throw new Error(payload?.error || `Request failed with status ${response.status}`);
    }

    return payload;
  };

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const payload = await requestJson('/api/tasks', { method: 'GET' });
      updateStoredTasks(payload.data);
    } catch (error) {
      console.error('API Error:', error);
      const saved = localStorage.getItem(TASKS_STORAGE_KEY);
      if (saved) {
        setTasks(JSON.parse(saved));
        toast.info('Using locally saved tasks');
      } else {
        toast.error('Unable to reach the backend right now');
      }
    } finally {
      setLoading(false);
    }
  };

  const createTask = async (taskData) => {
    try {
      const payload = await requestJson('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(taskData),
      });

      updateStoredTasks((currentTasks) => [...currentTasks, payload.data]);
      toast.success('Task created successfully!');
      return payload.data;
    } catch (error) {
      console.error('Create error:', error);
      toast.error(error.message || 'Failed to create task');
      return null;
    }
  };

  const updateTask = async (id, updates) => {
    try {
      const payload = await requestJson(`/api/tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      });

      updateStoredTasks((currentTasks) =>
        currentTasks.map((task) => (task._id === id ? payload.data : task))
      );
      toast.success('Task updated successfully!');
      return payload.data;
    } catch (error) {
      console.error('Update error:', error);
      toast.error(error.message || 'Failed to update task');
      return null;
    }
  };

  const deleteTask = async (id) => {
    try {
      await requestJson(`/api/tasks/${id}`, {
        method: 'DELETE',
      });

      updateStoredTasks((currentTasks) => currentTasks.filter((task) => task._id !== id));
      toast.success('Task deleted successfully!');
      return true;
    } catch (error) {
      console.error('Delete error:', error);
      toast.error(error.message || 'Failed to delete task');
      return false;
    }
  };

  const seedSampleTasks = async () => {
    try {
      const payload = await requestJson('/api/tasks/seed', {
        method: 'POST',
        body: JSON.stringify({ replace: true }),
      });

      updateStoredTasks(payload.data);
      toast.success('Sample data loaded from the backend');
      return payload.data;
    } catch (error) {
      console.error('Seed error:', error);
      toast.error(error.message || 'Failed to load sample data');
      return null;
    }
  };

  return (
    <Router>
      <div className="min-h-screen bg-gray-900 text-white">
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route
              path="/kanban"
              element={
                <KanbanBoard
                  tasks={tasks}
                  loading={loading}
                  onRefreshTasks={fetchTasks}
                  onSeedSampleData={seedSampleTasks}
                  onDeleteTask={deleteTask}
                />
              }
            />
            <Route
              path="/task/:id"
              element={
                <TaskDetails
                  tasks={tasks}
                  onCreateTask={createTask}
                  onUpdateTask={updateTask}
                  onDeleteTask={deleteTask}
                />
              }
            />
            <Route path="/about" element={<About />} />
          </Routes>
        </main>
        <Footer />
        <ToastContainer
          position="top-right"
          autoClose={3000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
          theme="dark"
        />
      </div>
    </Router>
  );
}

export default App;
