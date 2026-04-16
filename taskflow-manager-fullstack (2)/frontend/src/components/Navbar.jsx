import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, Plus } from 'lucide-react';

function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();

  const navItems = [
    { name: 'Home', path: '/' },
    { name: 'Kanban Board', path: '/kanban' },
    { name: 'About', path: '/about' }
  ];

  return (
    <nav className="sticky top-0 z-50 bg-gray-950/80 backdrop-blur-xl border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-r from-emerald-500 to-teal-400 rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-sm">TF</span>
            </div>
            <span className="text-white font-black text-xl bg-gradient-to-r from-emerald-500 to-teal-400 bg-clip-text text-transparent">
              TaskFlow
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {navItems.map((item) => (
              <Link
                key={item.name}
                to={item.path}
                className={`text-gray-400 hover:text-white transition-colors font-medium ${
                  location.pathname === item.path ? 'text-white' : ''
                }`}
              >
                {item.name}
              </Link>
            ))}
            <Link
              to="/task/new"
              className="bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-5 py-2 rounded-xl hover:scale-105 transition-all duration-300 text-sm flex items-center space-x-2"
            >
              <Plus size={16} />
              <span>New Task</span>
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              {isOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isOpen && (
          <div className="md:hidden border-t border-white/10 mt-2 pt-4 pb-4">
            <div className="flex flex-col space-y-4">
              {navItems.map((item) => (
                <Link
                  key={item.name}
                  to={item.path}
                  className={`text-gray-400 hover:text-white transition-colors font-medium ${
                    location.pathname === item.path ? 'text-white' : ''
                  }`}
                  onClick={() => setIsOpen(false)}
                >
                  {item.name}
                </Link>
              ))}
              <Link
                to="/task/new"
                className="bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-5 py-2 rounded-xl hover:scale-105 transition-all duration-300 text-sm flex items-center space-x-2 justify-center"
                onClick={() => setIsOpen(false)}
              >
                <Plus size={16} />
                <span>New Task</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

export default Navbar;