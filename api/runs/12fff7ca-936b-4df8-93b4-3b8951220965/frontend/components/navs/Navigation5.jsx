import React from "react";

const Navigation5 = ({ items = ["Discover Stays", "Sign In", "Host Dashboard", "Bookings", "Account Settings"], active = "Dashboard", onSelect = () => {} }) => {
  return (
    <nav className="p-4 bg-gray-100 shadow-md rounded-lg">
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className={`flex items-center py-2 px-3 cursor-pointer ${active === item ? "bg-blue-50 text-blue-600" : ""}`} onClick={() => onSelect(item)}>
            <span className="text-sm font-medium">{item}</span>
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default Navigation5;