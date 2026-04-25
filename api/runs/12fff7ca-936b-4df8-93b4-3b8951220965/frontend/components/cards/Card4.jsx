import React from "react";

const Card4 = ({ title, description, icon, action }) => {
  const defaultTitle = "Search Rooms";
  const defaultDescription = "Filter rooms by city, dates, and guest count.";
  const defaultIcon = <svg className="w-6 h-6" viewBox="0 0 24 24"><path fill="#000" d="M15.5 14h-.79l-.28-.27C15.41 12.54 16 11.63 16 10.5H9V5a2 2 0 00-2-2H5a2 2 0 00-2 2v1h.5c0 1.76.83 3.39 2.2 4.6l.5.5V14h-.01zm-6 0C6.01 14 5 12.99 5 12v-.5c0-.99.41-1.87 1.1-2.36L7 9.24l-.35-.38A1.998 1.998 0 015 8V6h.5a1 1 0 011 1v1H7v9h2v-1c0-.99.41-1.87 1.1-2.36L9 9.24l-.35-.38A1.998 1.998 0 007 8V6h.5a1 1 0 011 1v1H9zm6 0c0-1.76-.83-3.39-2.2-4.6L13.5 5.5V14z"/></svg>;
  const defaultAction = "Learn More";

  return (
    <div className="p-6 bg-white border-2 border-black shadow-[4px_4px_0_#000] rounded-md">
      {icon}
      <h3 className="mt-4 text-xl font-bold">{title || defaultTitle}</h3>
      <p className="mt-2 text-gray-700">{description || defaultDescription}</p>
      <button className="mt-6 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md">
        {action || defaultAction}
      </button>
    </div>
  );
};

export default Card4;