import React from "react";

const Navigation1 = ({ items = ["Discover Stays", "Host Dashboard", "Account Settings"], active = "Discover Stays", onSelect = () => {} }) => {
  return (
    <nav className="p-4 border-t border-gray-200">
      {items.map((item, index) => (
        <div
          key={index}
          onClick={() => onSelect(item)}
          className={`py-2 px-3 my-1 rounded cursor-pointer ${active === item ? 'bg-gray-100' : ''}`}
        >
          {item}
        </div>
      ))}
    </nav>
  );
};

export default Navigation1;