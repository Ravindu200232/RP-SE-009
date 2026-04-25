import React from "react";

const Header2 = ({ brand, navItems, ctaLabel, onCta }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds.", primary_color: "#2563eb" };
  const defaultNavItems = ["Discover", "My Trips", "Hosting", "Inbox", "Account"];
  const defaultCtaLabel = "Sign In";
  
  brand = { ...defaultBrand, ...brand };
  navItems = [...defaultNavItems, ...navItems];
  ctaLabel = ctaLabel || defaultCtaLabel;

  return (
    <header className="bg-blue-500 text-white shadow-lg rounded-2xl p-4">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-xl font-bold">{brand.name}</h1>
        <nav className="space-x-6">
          {navItems.map((item, index) => (
            <a key={index} href="#" className="hover:underline hover:text-gray-300">
              {item}
            </a>
          ))}
        </nav>
        <button onClick={() => onCta && onCta()} className="bg-white text-blue-500 rounded-xl px-4 py-2 font-bold shadow-md">
          {ctaLabel}
        </button>
      </div>
    </header>
  );
};

export default Header2;