import React from "react";

const Header1 = ({ brand, navItems, ctaLabel, onCta }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds.", primary_color: "#2563eb" };
  const defaultNavItems = ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard", "Reviews"];
  const defaultCtaLabel = "Sign In";

  brand = { ...defaultBrand, ...brand };
  navItems = [...defaultNavItems, ...navItems];
  ctaLabel = ctaLabel || defaultCtaLabel;

  return (
    <header className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
      <div className="text-xl font-bold text-blue-700">{brand.name}</div>
      <nav className="hidden md:flex space-x-6">
        {navItems.map((item, index) => (
          <a key={index} href="#" className="hover:underline hover:text-gray-900">
            {item}
          </a>
        ))}
      </nav>
      <button onClick={() => onCta && onCta()} className="text-blue-700 hover:text-blue-500 px-4 py-2 rounded-md border border-blue-300">
        {ctaLabel}
      </button>
    </header>
  );
};

export default Header1;