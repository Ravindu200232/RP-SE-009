import React from "react";

const Footer5 = ({ brand, columns, social, copyright }) => {
  const defaultBrand = { name: "BookStay", tagline: "Find your next stay in seconds." };
  const defaultColumns = [
    { title: "Discover Stays", links: ["landing"] },
    { title: "My Trips", links: ["table"] },
    { title: "Hosting", links: ["dashboard"] },
    { title: "Inbox", links: ["settings"] }
  ];
  const defaultSocial = [
    { name: "Facebook", link: "#" },
    { name: "Twitter", link: "#" },
    { name: "Instagram", link: "#" }
  ];
  const defaultCopyright = `${defaultBrand.name} - ${brand?.project_name}`;

  brand = brand || defaultBrand;
  columns = columns || defaultColumns;
  social = social || defaultSocial;
  copyright = copyright || defaultCopyright;

  return (
    <footer className="bg-gray-100 text-gray-700 py-6">
      <div className="container mx-auto px-4 grid grid-cols-4 gap-x-8">
        {columns.map((column, index) => (
          <div key={index} className="text-sm font-medium">
            <h3 className="mb-2">{column.title}</h3>
            <ul>
              {column.links.map(linkId => (
                <li key={linkId} className="mb-1">
                  <a href={`/${linkId}`} className="hover:underline text-gray-700 transition duration-150 ease-in-out">
                    {linkId.charAt(0).toUpperCase() + linkId.slice(1)}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <hr className="border-t border-gray-300 my-6" />
      <div className="container mx-auto px-4 flex justify-between items-center">
        <div className="text-sm font-medium">
          <a href="/" className="hover:underline text-blue-500 transition duration-150 ease-in-out">
            {brand.name}
          </a>
          <p className="mt-2">{brand.tagline}</p>
        </div>
        <ul className="flex space-x-4">
          {social.map((item, index) => (
            <li key={index} className="text-sm font-medium">
              <a href={item.link} target="_blank" rel="noopener noreferrer" className="hover:underline text-gray-700 transition duration-150 ease-in-out">
                {item.name}
              </a>
            </li>
          ))}
        </ul>
      </div>
      <hr className="border-t border-gray-300 my-6" />
      <p className="container mx-auto px-4 text-sm font-medium text-center">{copyright}</p>
    </footer>
  );
};

export default Footer5;