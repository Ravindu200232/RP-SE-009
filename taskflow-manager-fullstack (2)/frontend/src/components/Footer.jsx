import React from 'react';
import { Link } from 'react-router-dom';
import { Github, Twitter, Mail } from 'lucide-react';

function Footer() {
  return (
    <footer className="bg-gray-950 border-t border-white/10 py-16 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="col-span-1 md:col-span-2">
            <Link to="/" className="flex items-center space-x-2 mb-4">
              <div className="w-8 h-8 bg-gradient-to-r from-emerald-500 to-teal-400 rounded-lg flex items-center justify-center">
                <span className="text-white font-black text-sm">TF</span>
              </div>
              <span className="text-white font-black text-xl bg-gradient-to-r from-emerald-500 to-teal-400 bg-clip-text text-transparent">
                TaskFlow
              </span>
            </Link>
            <p className="text-gray-400 text-sm max-w-md">
              A modern task management application designed to help you organize your work 
              with intuitive drag-and-drop features and beautiful dark UI.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="text-white font-semibold mb-4">Navigation</h3>
            <ul className="space-y-2">
              <li><Link to="/" className="text-gray-400 hover:text-white transition-colors text-sm">Home</Link></li>
              <li><Link to="/kanban" className="text-gray-400 hover:text-white transition-colors text-sm">Kanban Board</Link></li>
              <li><Link to="/task/new" className="text-gray-400 hover:text-white transition-colors text-sm">New Task</Link></li>
              <li><Link to="/about" className="text-gray-400 hover:text-white transition-colors text-sm">About</Link></li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="text-white font-semibold mb-4">Connect</h3>
            <div className="flex space-x-4">
              <a href="#" className="text-gray-400 hover:text-white transition-colors">
                <Github size={20} />
              </a>
              <a href="#" className="text-gray-400 hover:text-white transition-colors">
                <Twitter size={20} />
              </a>
              <a href="#" className="text-gray-400 hover:text-white transition-colors">
                <Mail size={20} />
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;