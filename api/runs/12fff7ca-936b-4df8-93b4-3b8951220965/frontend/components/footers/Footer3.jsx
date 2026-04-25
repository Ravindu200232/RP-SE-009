import React from "react";

const Footer3 = ({ brand, columns, social, copyright }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultColumns = [
    { title: "Features", links: ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard", "Reviews"] },
    { title: "Company", links: ["About Us", "Blog", "Careers", "Press Kit"] },
    { title: "Legal", links: ["Privacy Policy", "Terms of Service", "Cookie Policy"] }
  ];
  const defaultSocial = [
    { name: "facebook", url: "#" },
    { name: "twitter", url: "#" },
    { name: "instagram", url: "#" }
  ];
  const defaultCopyright = `© ${new Date().getFullYear()} BookStay`;

  brand = brand || defaultBrand;
  columns = columns || defaultColumns;
  social = social || defaultSocial;
  copyright = copyright || defaultCopyright;

  return (
    <footer className="bg-white/30 backdrop-blur-sm p-8 rounded-lg text-gray-900">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-y-8 md:gap-x-6">
        {/* Brand Column */}
        <div>
          <h2 className="text-xl font-semibold mb-3">{brand.name}</h2>
          <p className="mb-6 text-gray-700">{brand.tagline}</p>
          <ul className="flex space-x-4">
            {social.map((item, index) => (
              <li key={index}>
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-600 transition duration-150 ease-in-out">
                  {item.name}
                </a>
              </li>
            ))}
          </ul>
        </div>

        {/* Link Columns */}
        {columns.map((column, index) => (
          <div key={index}>
            <h3 className="text-lg font-semibold mb-4">{column.title}</h3>
            <ul className="space-y-2">
              {column.links.map((link, linkIndex) => (
                <li key={linkIndex} className="hover:underline hover:text-blue-500 transition duration-150 ease-in-out">
                  <a href={`/${link.toLowerCase().replace(/ /g, '-')}`} className="text-gray-700">{link}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {/* Copyright Column */}
        <div className="col-span-4 md:col-span-1 text-center md:text-right">
          <p>{copyright}</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer3;