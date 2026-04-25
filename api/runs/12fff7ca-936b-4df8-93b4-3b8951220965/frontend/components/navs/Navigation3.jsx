import React from "react";

const Navigation3 = ({ items = ["Discover Stays", "My Trips", "Hosting", "Inbox", "Account"], active = "Discover Stays", onSelect = () => {} }) => {
  return (
    <nav className="fixed top-0 left-0 w-full h-screen bg-white/30 backdrop-blur-sm p-4 overflow-y-auto">
      <ul className="space-y-6 text-gray-900">
        {items.map((item, index) => (
          <li key={index} onClick={() => onSelect(item)} className={`cursor-pointer transition-all duration-200 ${active === item ? 'bg-blue-500/30' : ''}`}>
            <div className="flex items-center justify-between p-4 rounded-lg border-l-8 border-transparent">
              {item}
              {active === item && (
                <span className="ml-2 bg-white px-1 text-xs font-bold rounded-full">Active</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navigation3;