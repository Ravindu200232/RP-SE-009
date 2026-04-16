import React, { useMemo, useState } from 'react';
import { Plus, Calendar, RefreshCw, Database, Edit, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';

const columns = {
  todo: { title: 'To Do', color: 'bg-gray-500' },
  'in-progress': { title: 'In Progress', color: 'bg-blue-500' },
  done: { title: 'Done', color: 'bg-emerald-500' },
};

const formatStatus = (status) => columns[status]?.title || status;

function KanbanBoard({ tasks, loading, onRefreshTasks, onSeedSampleData, onDeleteTask }) {
  const [showModal, setShowModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPriority, setFilterPriority] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');

  const priorityColors = {
    low: 'bg-blue-500',
    medium: 'bg-amber-500',
    high: 'bg-red-500',
  };

  const filteredTasks = useMemo(
    () =>
      tasks.filter((task) => {
        const searchableText = [task.title, task.description || ''].join(' ').toLowerCase();
        const matchesSearch = searchableText.includes(searchTerm.toLowerCase());
        const matchesPriority = filterPriority === 'all' || task.priority === filterPriority;
        const matchesStatus = filterStatus === 'all' || task.status === filterStatus;
        return matchesSearch && matchesPriority && matchesStatus;
      }),
    [tasks, searchTerm, filterPriority, filterStatus]
  );

  const handleDelete = async (taskId) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      const deleted = await onDeleteTask(taskId);
      if (deleted) {
        setShowModal(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between mb-4">
            <div>
              <h1 className="text-4xl font-black text-white mb-2">Kanban Board</h1>
              <p className="text-gray-400">
                Live tasks from the backend with quick refresh and sample data loading.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onRefreshTasks}
                className="border border-white/10 text-white px-4 py-3 rounded-xl hover:bg-white/5 transition-colors text-sm flex items-center space-x-2"
              >
                <RefreshCw size={16} />
                <span>Refresh</span>
              </button>
              <button
                type="button"
                onClick={onSeedSampleData}
                className="border border-emerald-500/40 text-emerald-300 px-4 py-3 rounded-xl hover:bg-emerald-500/10 transition-colors text-sm flex items-center space-x-2"
              >
                <Database size={16} />
                <span>Load Sample Data</span>
              </button>
              <Link
                to="/task/new"
                className="bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-6 py-3 rounded-xl hover:scale-105 transition-all duration-300 text-sm flex items-center space-x-2"
              >
                <Plus size={16} />
                <span>New Task</span>
              </Link>
            </div>
          </div>

          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <input
              type="text"
              placeholder="Search tasks..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              className="bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 flex-1"
            />

            <select
              value={filterPriority}
              onChange={(event) => setFilterPriority(event.target.value)}
              className="bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Priorities</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>

            <select
              value={filterStatus}
              onChange={(event) => setFilterStatus(event.target.value)}
              className="bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Status</option>
              <option value="todo">To Do</option>
              <option value="in-progress">In Progress</option>
              <option value="done">Done</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Object.entries(columns).map(([statusKey, column]) => (
            <div
              key={statusKey}
              className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-white/10"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 ${column.color} rounded-full`} />
                  <h2 className="text-white font-semibold">{column.title}</h2>
                </div>
                <span className="bg-white/10 text-white text-sm px-3 py-1 rounded-full">
                  {filteredTasks.filter((task) => task.status === statusKey).length}
                </span>
              </div>

              <div className="space-y-4">
                {filteredTasks
                  .filter((task) => task.status === statusKey)
                  .map((task) => (
                    <div
                      key={task._id}
                      className="bg-gray-700/50 backdrop-blur-lg rounded-xl p-4 border border-white/10 hover:border-emerald-500/30 transition-all duration-300 cursor-pointer"
                      onClick={() => {
                        setSelectedTask(task);
                        setShowModal(true);
                      }}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <h3 className="text-white font-semibold text-sm line-clamp-2">{task.title}</h3>
                        <div
                          className={`w-2 h-2 ${
                            priorityColors[task.priority] || 'bg-gray-500'
                          } rounded-full flex-shrink-0 mt-1`}
                        />
                      </div>

                      <p className="text-gray-400 text-xs mb-3 line-clamp-3">
                        {task.description || 'No description added yet.'}
                      </p>

                      {task.deadline && (
                        <div className="flex items-center space-x-1 text-gray-400 text-xs">
                          <Calendar size={12} />
                          <span>{new Date(task.deadline).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>
                  ))}

                {filteredTasks.filter((task) => task.status === statusKey).length === 0 && (
                  <div className="text-gray-400 text-sm text-center py-8">No tasks in this column</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {showModal && selectedTask && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-gray-800 border border-white/10 rounded-2xl p-6 max-w-md w-full">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-white font-bold text-lg">{selectedTask.title}</h2>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  x
                </button>
              </div>

              <p className="text-gray-400 text-sm mb-4">
                {selectedTask.description || 'No description added yet.'}
              </p>

              <div className="space-y-3 mb-6">
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-3 h-3 ${
                      priorityColors[selectedTask.priority] || 'bg-gray-500'
                    } rounded-full`}
                  />
                  <span className="text-white text-sm capitalize">
                    {selectedTask.priority} Priority
                  </span>
                </div>

                <div className="flex items-center space-x-2">
                  <div
                    className={`w-3 h-3 ${
                      (columns[selectedTask.status] || columns.todo).color
                    } rounded-full`}
                  />
                  <span className="text-white text-sm">{formatStatus(selectedTask.status)}</span>
                </div>

                {selectedTask.deadline && (
                  <div className="flex items-center space-x-2">
                    <Calendar size={14} className="text-gray-400" />
                    <span className="text-gray-400 text-sm">
                      Due: {new Date(selectedTask.deadline).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              <div className="flex space-x-3">
                <Link
                  to={`/task/${selectedTask._id}`}
                  className="bg-emerald-500 text-white font-medium px-4 py-2 rounded-xl hover:bg-emerald-600 transition-colors text-sm flex items-center space-x-2 flex-1 justify-center"
                >
                  <Edit size={14} />
                  <span>Edit</span>
                </Link>

                <button
                  type="button"
                  onClick={() => handleDelete(selectedTask._id)}
                  className="bg-red-500 text-white font-medium px-4 py-2 rounded-xl hover:bg-red-600 transition-colors text-sm flex items-center space-x-2 flex-1 justify-center"
                >
                  <Trash2 size={14} />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default KanbanBoard;
