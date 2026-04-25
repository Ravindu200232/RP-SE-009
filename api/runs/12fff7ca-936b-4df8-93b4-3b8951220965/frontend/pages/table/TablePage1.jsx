import React from "react";

const TablePage1 = () => {
  return (
    <div className="bg-white">
      <header className="p-4 border-b border-gray-200 flex justify-between items-center">
        <h1 className="text-xl font-semibold text-gray-900">Bookings</h1>
        <button className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none">
          New Booking
        </button>
      </header>

      <div className="p-4 border-b border-gray-200 flex justify-between items-center">
        <form className="flex space-x-3">
          <input type="text" placeholder="Search bookings..." className="border p-2 rounded w-64 focus:outline-none" />
          <button className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none">
            Search
          </button>
        </form>

        <div className="flex space-x-3">
          <select className="border p-2 rounded w-48 focus:outline-none">
            <option value="all">All</option>
            <option value="confirmed">Confirmed</option>
            <option value="pending">Pending</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <button className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none">
            Filter
          </button>
        </div>
      </div>

      <table className="min-w-full border-t border-gray-200 mt-4">
        <thead className="bg-gray-100">
          <tr>
            <th className="py-3 px-6 text-left">Booking ID</th>
            <th className="py-3 px-6 text-left">Guest Name</th>
            <th className="py-3 px-6 text-left">Check-In Date</th>
            <th className="py-3 px-6 text-left">Check-Out Date</th>
            <th className="py-3 px-6 text-left">Room Type</th>
            <th className="py-3 px-6 text-right">Total Amount</th>
          </tr>
        </thead>

        <tbody>
          <tr className="border-b border-gray-200">
            <td className="py-4 px-6 text-sm font-medium text-gray-900 whitespace-nowrap">12345</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">John Doe</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">2023-10-01</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">2023-10-05</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">Deluxe Room</td>
            <td className="py-4 px-6 text-right">$299.99</td>
          </tr>

          <tr className="border-b border-gray-200">
            <td className="py-4 px-6 text-sm font-medium text-gray-900 whitespace-nowrap">12346</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">Jane Smith</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">2023-10-05</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">2023-10-10</td>
            <td className="py-4 px-6 text-sm text-gray-700 whitespace-nowrap">Suite Room</td>
            <td className="py-4 px-6 text-right">$599.99</td>
          </tr>

          {/* Add more rows as needed */}
        </tbody>
      </table>

      <div className="p-4 flex justify-between items-center">
        <nav aria-label="Page navigation" className="flex space-x-3">
          <button className="px-3 py-2 bg-gray-50 text-blue-600 rounded hover:bg-gray-100 focus:outline-none">Previous</button>
          <span className="text-sm font-medium text-gray-700">Page 1 of 4</span>
          <button className="px-3 py-2 bg-gray-50 text-blue-600 rounded hover:bg-gray-100 focus:outline-none">Next</button>
        </nav>

        <div className="flex space-x-3">
          <select className="border p-2 rounded w-48 focus:outline-none">
            <option value="10">10 per page</option>
            <option value="25">25 per page</option>
            <option value="50">50 per page</option>
          </select>

          <button className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 focus:outline-none">
            Export
          </button>
        </div>
      </div>
    </div>
  );
};

export default TablePage1;