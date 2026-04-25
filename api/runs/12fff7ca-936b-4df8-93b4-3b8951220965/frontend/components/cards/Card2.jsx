import React from "react";

const Card2 = ({ title = "Search Rooms", description = "Filter rooms by city, dates, and guest count.", icon = <svg className="w-6 h-6 text-white fill-current" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.54 16 11.63 16 10.5 16 9.17 14.83 6 12 6c-4.42 0-7.6 3.18-7.6 7.6 0 1.72.66 3.22 1.7 4.5v-.9a.5.5 0 0 1 .5-.5h2c0 .21.16.4.35.4.18 0 .34-.1.4-.25l.06-.06zm-1.71 2.46a.5.5 0 0 1-.71.71 15.99 15.99 0 0 1-2.16-.87.5.5 0 0 1 .71-.71 15.99 15.99 0 0 1 2.16.87zm4.33-4a.5.5 0 0 1-.71.71 15.99 15.99 0 0 1-2.16-.87.5.5 0 0 1 .71-.71 15.99 15.99 0 0 1 2.16.87zm4.33-4a.5.5 0 0 1-.71.71 15.99 15.99 0 0 1-2.16-.87.5.5 0 0 1 .71-.71 15.99 15.99 0 0 1 2.16.87z"/></svg>, action = "Learn More" }) => {
  return (
    <div className="bg-blue-600 rounded-2xl shadow-lg p-4">
      {icon}
      <h2 className="text-xl font-bold mt-2 text-white">{title}</h2>
      <p className="mt-1 text-gray-300">{description}</p>
      <button className="mt-4 px-4 py-2 bg-blue-700 rounded-lg hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-opacity-50">
        {action}
      </button>
    </div>
  );
}

export default Card2;