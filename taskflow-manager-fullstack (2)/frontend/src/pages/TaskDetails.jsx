import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Save, Trash2 } from 'lucide-react';
import { toast } from 'react-toastify';

function TaskDetails({ tasks, onCreateTask, onUpdateTask, onDeleteTask }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEditing = id && id !== 'new';

  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: 'medium',
    status: 'todo',
    deadline: '',
  });

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isEditing) {
      const task = tasks.find((item) => item._id === id);
      if (task) {
        setFormData({
          title: task.title || '',
          description: task.description || '',
          priority: task.priority || 'medium',
          status: task.status || 'todo',
          deadline: task.deadline ? new Date(task.deadline).toISOString().split('T')[0] : '',
        });
      }
    }
  }, [id, isEditing, tasks]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);

    try {
      const taskData = {
        ...formData,
        deadline: formData.deadline ? new Date(formData.deadline).toISOString() : null,
      };

      if (isEditing) {
        const updatedTask = await onUpdateTask(id, taskData);
        if (!updatedTask) {
          return;
        }
      } else {
        const createdTask = await onCreateTask(taskData);
        if (!createdTask) {
          return;
        }
      }

      navigate('/kanban');
    } catch (error) {
      toast.error('Failed to save task');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      const deleted = await onDeleteTask(id);
      if (deleted) {
        navigate('/kanban');
      }
    }
  };

  const handleChange = (event) => {
    setFormData((currentFormData) => ({
      ...currentFormData,
      [event.target.name]: event.target.value,
    }));
  };

  return (
    <div className="min-h-screen bg-gray-900 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <Link
            to="/kanban"
            className="text-gray-400 hover:text-white transition-colors flex items-center space-x-2"
          >
            <ArrowLeft size={20} />
            <span>Back to Board</span>
          </Link>

          <h1 className="text-3xl font-black text-white">
            {isEditing ? 'Edit Task' : 'Create New Task'}
          </h1>

          {isEditing && (
            <button
              type="button"
              onClick={handleDelete}
              className="text-red-400 hover:text-red-300 transition-colors flex items-center space-x-2"
            >
              <Trash2 size={20} />
              <span>Delete</span>
            </button>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-white/10"
        >
          <div className="space-y-6">
            <div>
              <label className="block text-white font-medium mb-2">Title</label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                className="w-full bg-gray-700 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                placeholder="Enter task title"
              />
            </div>

            <div>
              <label className="block text-white font-medium mb-2">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={4}
                className="w-full bg-gray-700 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                placeholder="Enter task description"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-white font-medium mb-2">Priority</label>
                <select
                  name="priority"
                  value={formData.priority}
                  onChange={handleChange}
                  className="w-full bg-gray-700 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div>
                <label className="block text-white font-medium mb-2">Status</label>
                <select
                  name="status"
                  value={formData.status}
                  onChange={handleChange}
                  className="w-full bg-gray-700 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="todo">To Do</option>
                  <option value="in-progress">In Progress</option>
                  <option value="done">Done</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-white font-medium mb-2">Deadline (Optional)</label>
              <input
                type="date"
                name="deadline"
                value={formData.deadline}
                onChange={handleChange}
                className="w-full bg-gray-700 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-6 py-4 rounded-xl hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                <>
                  <Save size={20} />
                  <span>{isEditing ? 'Update Task' : 'Create Task'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default TaskDetails;
