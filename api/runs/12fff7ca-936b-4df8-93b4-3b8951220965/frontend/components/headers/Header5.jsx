import React from "react";

const Header5 = ({ brand, navItems, ctaLabel, onCta }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultNavItems = ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard"];
  const defaultCtaLabel = "Sign In";
  
  brand = brand || defaultBrand;
  navItems = navItems || defaultNavItems;
  ctaLabel = ctaLabel || defaultCtaLabel;

  return (
    <header className="bg-gray-100 text-blue-900 py-4 shadow-md">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-xl font-serif tracking-wide">{brand.name}</h1>
        <nav className="flex space-x-6">
          {navItems.map((item, index) => (
            <a key={index} href="#" className="hover:underline hover:text-blue-700">
              {item}
            </a>
          ))}
        </nav>
        <button onClick={() => onCta && onCta()} className="bg-blue-500 text-white px-4 py-2 rounded-md shadow-sm hover:bg-blue-600 focus:outline-none">
          {ctaLabel}
        </button>
      </div>
    </header>
  );
};

export default Header5;