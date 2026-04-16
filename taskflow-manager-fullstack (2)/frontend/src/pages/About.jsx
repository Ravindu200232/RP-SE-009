import React from 'react';
import { Users, Heart, Code, Palette } from 'lucide-react';

function About() {
  const teamMembers = [
    {
      name: "Alex Chen",
      role: "Frontend Developer",
      bio: "Passionate about creating beautiful and intuitive user interfaces with React and modern web technologies."
    },
    {
      name: "Maria Rodriguez",
      role: "Backend Engineer",
      bio: "Specializes in building scalable APIs and database architectures with Node.js and MongoDB."
    },
    {
      name: "David Kim",
      role: "UI/UX Designer",
      bio: "Creates stunning visual experiences with a focus on user-centered design principles and accessibility."
    }
  ];

  const techStack = [
    { name: "React", description: "Modern frontend framework for building interactive UIs" },
    { name: "Node.js", description: "JavaScript runtime for building scalable backend services" },
    { name: "MongoDB", description: "NoSQL database for flexible data storage" },
    { name: "Tailwind CSS", description: "Utility-first CSS framework for rapid UI development" },
    { name: "Express", description: "Minimal web framework for Node.js applications" },
    { name: "React Beautiful DnD", description: "Beautiful drag and drop for lists with React" }
  ];

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Hero Section */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl md:text-7xl font-black text-white mb-6">
            About <span className="bg-gradient-to-r from-emerald-500 to-teal-400 bg-clip-text text-transparent">TaskFlow</span>
          </h1>
          <p className="text-xl text-gray-400 mb-8">
            We're building the future of task management with focus on simplicity, 
            productivity, and beautiful design.
          </p>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-16 px-4 bg-gray-950">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-white mb-4">Our Mission</h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              To help individuals and teams achieve their goals through intuitive 
              task management tools that just work.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Users className="text-emerald-400" size={32} />
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">User-First</h3>
              <p className="text-gray-400">Designed with real user needs in mind, not just features.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-teal-400/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Heart className="text-teal-300" size={32} />
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">Built with Love</h3>
              <p className="text-gray-400">Every pixel and line of code crafted with care and attention.</p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Code className="text-emerald-400" size={32} />
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">Open Source</h3>
              <p className="text-gray-400">Built on open technologies and committed to transparency.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-white mb-4">Meet the Team</h2>
            <p className="text-lg text-gray-400">
              Passionate developers and designers working together to build something amazing
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {teamMembers.map((member, index) => (
              <div
                key={index}
                className="bg-gray-900/50 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-center hover:-translate-y-2 hover:shadow-2xl hover:border-white/20 transition-all duration-300"
              >
                <div className="w-20 h-20 bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <span className="text-white font-bold text-xl">
                    {member.name.split(' ').map(n => n[0]).join('')}
                  </span>
                </div>
                <h3 className="text-white font-semibold text-lg mb-2">{member.name}</h3>
                <p className="text-emerald-400 text-sm mb-4">{member.role}</p>
                <p className="text-gray-400 text-sm">{member.bio}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tech Stack Section */}
      <section className="py-24 px-4 bg-gray-950">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-black text-white mb-4">Technology Stack</h2>
            <p className="text-lg text-gray-400">
              Built with modern technologies for optimal performance and developer experience
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {techStack.map((tech, index) => (
              <div
                key={index}
                className="bg-gray-900/50 backdrop-blur-sm border border-white/10 rounded-2xl p-6 hover:-translate-y-2 hover:shadow-2xl hover:border-white/20 transition-all duration-300"
              >
                <div className="flex items-center space-x-3 mb-3">
                  <div className="w-10 h-10 bg-emerald-500/20 rounded-lg flex items-center justify-center">
                    <Palette className="text-emerald-400" size={20} />
                  </div>
                  <h3 className="text-white font-semibold">{tech.name}</h3>
                </div>
                <p className="text-gray-400 text-sm">{tech.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl font-black text-white mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-gray-400 mb-10">
            Join thousands of users who have transformed their productivity with TaskFlow
          </p>
          <div className="flex gap-4 flex-wrap justify-center">
            <a
              href="/kanban"
              className="bg-gradient-to-r from-emerald-500 to-teal-400 text-white font-bold px-8 py-4 rounded-2xl shadow-lg hover:scale-105 transition-all duration-300 text-lg"
            >
              Start Using TaskFlow
            </a>
            <a
              href="#"
              className="border border-white/20 text-white font-bold px-8 py-4 rounded-2xl hover:bg-white/10 transition-all duration-300 text-lg backdrop-blur-sm"
            >
              View Source Code
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}

export default About;