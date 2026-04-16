import React from 'react';
import { Link } from 'react-router-dom';
import { Kanban, Calendar, Filter, Zap, ArrowRight } from 'lucide-react';

function Home() {
  const features = [
    {
      icon: <Kanban size={32} className="text-emerald-400" />,
      title: "Drag & Drop Kanban",
      description: "Organize tasks visually with intuitive drag-and-drop columns for To Do, In Progress, and Done."
    },
    {
      icon: <Calendar size={32} className="text-teal-400" />,
      title: "Smart Deadlines",
      description: "Set and track deadlines with color-coded priority levels and automatic reminders."
    },
    {
      icon: <Filter size={32} className="text-emerald-300" />,
      title: "Advanced Filtering",
      description: "Filter tasks by priority, status, or deadline to focus on what matters most."
    },
    {
      icon: <Zap size={32} className="text-teal-300" />,
      title: "Lightning Fast",
      description: "Built for speed with real-time updates and offline capabilities using local storage."
    }
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden px-4">
        {/* Animated gradient blobs */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/20 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-teal-400/20 rounded-full blur-3xl animate-pulse delay-1000" />
        </div>
        
        <h1 className="text-6xl md:text-8xl font-black text-center mb-6 bg-gradient-to-r from-emerald-500 to-teal-400 bg-clip-text text-transparent leading-tight">
          TaskFlow
        </h1>
        <p className="text-xl text-gray-400 text-center max-w-2xl mb-10">
          The modern way to manage your tasks. Beautiful, intuitive, and powerful.
        </p>
        
        <div className="flex gap-4 flex-wrap justify-center">
          <Link
            to="/kanban"
            className="bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-8 py-4 rounded-2xl shadow-lg hover:scale-105 transition-all duration-300 text-lg flex items-center space-x-2"
          >
            <span>Get Started</span>
            <ArrowRight size={20} />
          </Link>
          <Link
            to="/about"
            className="border border-white/20 text-white font-bold px-8 py-4 rounded-2xl hover:bg-white/10 transition-all duration-300 text-lg"
          >
            Learn More
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-4xl font-black text-white text-center mb-16">
            Why Choose TaskFlow?
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div key={index} className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:border-emerald-500/30 transition-all duration-300">
                <div className="mb-4">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export default Home;