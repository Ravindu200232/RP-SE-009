import React from "react";

const Card3 = ({ title, description, icon, action }) => {
  const defaultTitle = "Search Rooms";
  const defaultDescription = "Filter rooms by city, dates, and guest count.";
  const defaultIcon = <svg className="w-6 h-6" viewBox="0 0 24 24"><path fill="#2563eb" d="M18.75 19h-15v-2h15zM19 9H5V5h14z"/></svg>;
  const defaultAction = "Learn More";

  return (
    <div className="p-6 rounded-lg bg-white/30 backdrop-blur-md shadow-md flex flex-col items-center space-y-4">
      {icon}
      <div className="text-xl font-semibold text-blue-500">{title || defaultTitle}</div>
      <div className="text-gray-700 text-sm leading-relaxed">{description || defaultDescription}</div>
      <button className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors ease-in-out duration-300">
        {action || defaultAction}
      </button>
    </div>
  );
};

export default Card3;