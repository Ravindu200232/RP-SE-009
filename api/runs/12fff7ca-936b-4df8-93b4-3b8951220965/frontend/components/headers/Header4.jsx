import React from "react";

const Header4 = ({ brand, navItems, ctaLabel, onCta }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultNavItems = ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard"];
  const defaultProps = { brand: defaultBrand, navItems: defaultNavItems, ctaLabel: "Sign In" };

  return (
    <header className="bg-white border-b-2 border-black shadow-[4px_4px_0_#000] p-4">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-xl font-bold text-gray-900">{defaultProps.brand.name}</h1>
        <nav className="flex space-x-6">
          {navItems.map((item, index) => (
            <a key={index} href="#" className="text-sm text-black hover:underline">
              {item}
            </a>
          ))}
        </nav>
        <button onClick={() => onCta && onCta()} className="px-4 py-2 bg-blue-600 text-white rounded-md shadow-[4px_4px_0_#000]">
          {ctaLabel}
        </button>
      </div>
    </header>
  );
};

export default Header4;