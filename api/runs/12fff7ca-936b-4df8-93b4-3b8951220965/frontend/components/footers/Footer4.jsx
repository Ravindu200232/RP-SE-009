import React from "react";

const Footer4 = ({ brand, columns, social, copyright }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds.", primary_color: "#2563eb" };
  const defaultColumns = [
    { title: "Features", links: ["Search Rooms", "Room Details", "Secure Checkout", "Host Dashboard", "Reviews"] },
    { title: "Navigation", links: ["Discover", "My Trips", "Hosting", "Inbox", "Account"] }
  ];
  const defaultSocial = [{ name: "Facebook", url: "#" }, { name: "Twitter", url: "#" }];
  const defaultCopyright = `${defaultBrand.name} ${new Date().getFullYear()}`;

  brand = brand || defaultBrand;
  columns = columns || defaultColumns;
  social = social || defaultSocial;
  copyright = copyright || defaultCopyright;

  return (
    <footer className="bg-white border-t-2 border-black shadow-[4px_4px_0_black] p-8">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {columns.map((column, index) => (
          <div key={index} className="space-y-4">
            <h5 className="text-lg font-bold text-black">{column.title}</h5>
            <ul className="space-y-2">
              {column.links.map(link => (
                <li key={link}>
                  <a href="#" className="text-sm text-gray-600 hover:underline">
                    {link}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="mt-8 border-t-2 border-black pt-4 flex justify-between items-center">
        <p className="text-sm text-gray-600">{copyright}</p>
        <div className="flex space-x-4">
          {social.map((item, index) => (
            <a key={index} href={item.url} className="text-sm text-black hover:underline">
              {item.name}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
};

export default Footer4;