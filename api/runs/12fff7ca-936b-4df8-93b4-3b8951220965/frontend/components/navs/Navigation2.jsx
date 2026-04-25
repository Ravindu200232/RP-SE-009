import React from "react";

const Navigation2 = ({ items = ["Discover Stays", "Sign In", "Host Dashboard", "Bookings", "Account Settings"], active = "Discover Stays", onSelect = () => {} }) => {
  return (
    <div className="p-4 rounded-2xl bg-primary shadow-lg">
      <ul className="space-y-3">
        {items.map((item, index) => (
          <li key={index} onClick={() => onSelect(item)} className={`cursor-pointer py-1 px-2 text-white font-bold ${active === item ? "bg-secondary" : ""}`}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Navigation2;