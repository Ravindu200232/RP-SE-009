import React from "react";

const Header3 = ({ brand, navItems, ctaLabel, onCta }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultNavItems = ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard"];
  const defaultCtaLabel = "Sign In";
  
  brand = brand || defaultBrand;
  navItems = navItems || defaultNavItems;
  ctaLabel = ctaLabel || defaultCtaLabel;

  return (
    <header className="bg-white/30 backdrop-blur-sm p-4 flex items-center justify-between rounded-lg shadow-md">
      <div className="flex items-center">
        <h1 className="text-xl font-bold text-blue-500 mr-2">{brand.name}</h1>
        <p className="text-gray-600 text-sm">{brand.tagline}</p>
      </div>
      <nav className="hidden md:flex space-x-4">
        {navItems.map((item, index) => (
          <a key={index} href="#" className="text-blue-500 hover:text-blue-700 transition-colors duration-200">{item}</a>
        ))}
      </nav>
      <button onClick={() => onCta && onCta()} className="bg-blue-500 text-white px-4 py-2 rounded-md shadow-sm hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-300 transition duration-150 ease-in-out">
        {ctaLabel}
      </button>
    </header>
  );
};

export default Header3;