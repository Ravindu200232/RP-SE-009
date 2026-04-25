import React from "react";

const TablePage3 = () => {
  return (
    <div className="bg-white/30 backdrop-blur-sm p-8 rounded-lg shadow-md max-w-screen-xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">BookStay</h1>
      <p className="text-gray-600 mb-8">{`Find your next stay in seconds.`}</p>

      <div className="mb-6">
        <label htmlFor="search" className="sr-only">
          Search
        </label>
        <input
          type="text"
          id="search"
          placeholder="Search bookings..."
          className="w-full p-2 border rounded-lg focus:outline-none focus:border-blue-500 bg-white/50"
        />
      </div>

      <table className="min-w-full divide-y divide-gray-300">
        <thead>
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Booking ID
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Guest Name
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Check-in Date
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Check-out Date
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Total Amount
            </th>
          </tr>
        </thead>

        <tbody>
          <tr>
            <td className="px-6 py-4 whitespace-nowrap">123</td>
            <td className="px-6 py-4 whitespace-nowrap">John Doe</td>
            <td className="px-6 py-4 whitespace-nowrap">2023-10-05</td>
            <td className="px-6 py-4 whitespace-nowrap">2023-10-15</td>
            <td className="px-6 py-4 whitespace-nowrap text-right">$129.99</td>
          </tr>

          {/* Additional rows can be added here */}
        </tbody>
      </table>

      <div className="flex justify-between items-center mt-8">
        <nav aria-label="Pagination" className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
          <a
            href="#"
            className="relative inline-flex items-center px-2 py-2 rounded-l-md border text-sm font-medium bg-white/50 hover:bg-blue-100 focus:z-20"
          >
            Previous
          </a>
          <a
            href="#"
            aria-current="page"
            className="bg-white/50 border relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-blue-100 focus:z-20"
          >
            1
          </a>
          <a href="#" className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-white/50 hover:bg-blue-100">
            2
          </a>
          <a href="#" className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-white/50 hover:bg-blue-100">
            3
          </a>
          <span className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-gray-50">...</span>
          <a href="#" className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-white/50 hover:bg-blue-100">
            8
          </a>
          <a href="#" className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-white/50 hover:bg-blue-100">
            9
          </a>
          <a href="#" className="relative inline-flex items-center px-4 py-2 border text-sm font-medium bg-white/50 hover:bg-blue-100">
            10
          </a>
          <a
            href="#"
            className="relative inline-flex items-center px-2 py-2 rounded-r-md border text-sm font-medium bg-white/50 hover:bg-blue-100 focus:z-20"
          >
            Next
          </a>
        </nav>

        <div className="flex items-center space-x-4">
          <button type="button" className="px-4 py-2 rounded-md text-sm font-medium bg-white/50 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-600">
            Export
          </button>
          <div className="relative inline-flex items-center px-3 py-2 border rounded-md cursor-pointer">
            <span className="text-sm font-medium">Rows per page</span>
            <select id="rowsPerPage" className="block w-full mt-1 text-gray-800 bg-white/50 focus:ring-blue-600 focus:border-blue-600">
              <option>10</option>
              <option>25</option>
              <option>50</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TablePage3;