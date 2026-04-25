import React from "react";

const Card1 = ({ title, description, icon, action }) => {
  const defaultTitle = "Search Rooms";
  const defaultDescription = "Filter rooms by city, dates, and guest count.";
  const defaultIcon = <span className="material-icons">search</span>;
  const defaultAction = { label: "Learn More", href: "#" };

  return (
    <div className="bg-white border p-4 rounded shadow-md hover:bg-gray-50 transition duration-150">
      <div className="flex items-center mb-2">
        {icon || defaultIcon}
        <span className="ml-2 font-semibold">{title || defaultTitle}</span>
      </div>
      <p className="text-gray-600 text-sm leading-relaxed">
        {description || defaultDescription}
      </p>
      {action && (
        <a href={action.href} className="block mt-4 text-blue-500 hover:underline">
          {action.label}
        </a>
      )}
    </div>
  );
};

export default Card1;