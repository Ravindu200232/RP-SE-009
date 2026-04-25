import React from "react";

const Footer2 = ({ brand, columns, social, copyright }) => {
  const defaultBrand = { name: "BookStay", primary_color: "#2563eb" };
  const defaultColumns = [
    { title: "Discover Stays", links: ["Search Rooms", "Room Details"] },
    { title: "Manage Your Booking", links: ["Secure Checkout", "Reviews"] },
    { title: "Host Dashboard", links: ["Host Dashboard"] }
  ];
  const defaultSocial = ["facebook", "twitter", "instagram"];
  const defaultCopyright = `${defaultBrand.name} ${new Date().getFullYear()}`;

  brand = brand || defaultBrand;
  columns = columns || defaultColumns;
  social = social || defaultSocial;
  copyright = copyright || defaultCopyright;

  return (
    <footer className="bg-primary-500 text-white p-8 rounded-2xl shadow-lg">
      <div className="grid grid-cols-3 gap-4">
        {columns.map((column, index) => (
          <div key={index} className="space-y-2">
            <h3 className="text-xl font-bold">{column.title}</h3>
            <ul className="space-y-1">
              {column.links.map((link, linkIndex) => (
                <li key={linkIndex}>
                  <a href={`/${link.toLowerCase().replace(/ /g, "-")}`} className="hover:underline hover:text-primary-400">
                    {link}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mt-8 flex justify-between items-center">
        <p className="text-lg font-bold">{brand.name}</p>
        <nav className="flex space-x-4">
          {social.map((platform, index) => (
            <a key={index} href={`https://www.${platform}.com`} target="_blank" rel="noopener noreferrer" className="hover:text-primary-300">
              {platform}
            </a>
          ))}
        </nav>
      </div>
      <p className="mt-4 text-center font-bold">{copyright}</p>
    </footer>
  );
};

export default Footer2;