import React from "react";

const Card5 = ({ title, description, icon, action }) => {
  const defaultTitle = "Search Rooms";
  const defaultDescription = "Filter rooms by city, dates, and guest count.";
  const defaultIcon = <svg className="w-6 h-6 text-gray-400" viewBox="0 0 24 24"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27C15.41 12.54 16 11.63 16 10.5H9V9.5C9 8.62 9.68 8 10.5 8H11v6l4-4zm-.5 6c-.25 0-.5-.2-.5-.41v-1.78l3.58-3.58L12 11.97l-1.29-.7c-.35-.2-.35-.8.01-1.01L16.51 9l.7-.7c.4-.4.4-.99 0-1.39L14.5 6h-3v1.79l-3.58 3.58L6 12.03l1.29.7c.35.2.35.8-.01 1.01l2.51 2.5V14z"/></svg>;
  const defaultAction = "Learn More";

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {icon}
      <h2 className="text-xl font-bold mt-4 text-blue-700">{title || defaultTitle}</h2>
      <p className="mt-2 text-gray-600">{description || defaultDescription}</p>
      <button className="mt-4 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded">
        {action || defaultAction}
      </button>
    </div>
  );
};

export default Card5;