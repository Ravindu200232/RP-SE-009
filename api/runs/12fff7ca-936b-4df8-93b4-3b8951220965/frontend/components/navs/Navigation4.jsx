import React from "react";

const Navigation4 = ({ items = ["Discover Stays", "Sign In", "Host Dashboard", "Bookings", "Account Settings"], active = "Dashboard", onSelect = () => {} }) => {
  return (
    <nav className="p-4 bg-white border-t-2 border-b-2 border-black shadow-[4px_4px_0_#000]">
      <ul className="space-y-2 text-lg font-mono">
        {items.map((item, index) => (
          <li key={index} onClick={() => onSelect(item)} className={`block px-4 py-2 ${active === item ? 'bg-black text-white' : 'hover:bg-gray-100'}`}>
            {item}
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navigation4;