import React from "react";

const Footer1 = ({ brand, columns, social, copyright }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultColumns = [
    { title: "Discover Stays", links: ["landing"] },
    { title: "Manage Listings", links: ["dashboard"] },
    { title: "Secure Checkout", links: ["table"] }
  ];
  const defaultSocial = [{ name: "Facebook" }, { name: "Instagram" }];
  const defaultCopyright = `© ${new Date().getFullYear()} BookStay`;

  brand = brand || defaultBrand;
  columns = columns || defaultColumns;
  social = social || defaultSocial;
  copyright = copyright || defaultCopyright;

  return (
    <footer className="bg-gray-100 text-gray-600 border-t border-gray-200 py-8">
      <div className="container mx-auto px-4 flex justify-between items-center">
        {/* Brand */}
        <div className="flex items-center space-x-2">
          <h3 className="text-lg font-bold">{brand.name}</h3>
          <p className="text-sm text-gray-500">{brand.tagline}</p>
        </div>

        {/* Columns */}
        <div className="hidden md:flex flex-grow justify-between w-full lg:w-auto space-x-4">
          {columns.map((column, index) => (
            <div key={index} className="space-y-2">
              <h5 className="text-sm font-semibold">{column.title}</h5>
              <ul className="list-none space-y-1 text-xs">
                {column.links.map(linkId => (
                  <li key={linkId}>
                    <a href={`/${linkId}`} className="hover:underline hover:text-gray-700">
                      {linkId}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Social Links */}
        <div className="flex space-x-2 text-sm font-medium">
          {social.map((item, index) => (
            <a key={index} href={`https://www.${item.name.toLowerCase()}.com`} target="_blank" rel="noopener noreferrer" className="hover:underline hover:text-gray-700">
              {item.name}
            </a>
          ))}
        </div>

        {/* Copyright */}
        <p className="text-sm text-gray-500">{copyright}</p>
      </div>
    </footer>
  );
};

export default Footer1;