import React from "react";

const TablePage2 = () => {
  return (
    <div className="bg-white rounded-2xl shadow-lg p-8">
      <h1 className="text-4xl font-bold text-blue-600 mb-4">BookStay</h1>
      <p className="text-xl font-semibold text-gray-700 mb-8">Host Dashboard - Bookings</p>

      {/* Filters Section */}
      <div className="mb-8">
        <label htmlFor="city" className="block text-lg font-bold text-blue-600 mb-2">
          City
        </label>
        <input type="text" id="city" placeholder="City" className="w-full p-3 rounded-xl bg-gray-100 border-none focus:outline-none focus:ring-2 focus:ring-blue-500" />

        <div className="mt-4">
          <label htmlFor="check-in-date" className="block text-lg font-bold text-blue-600 mb-2">
            Check-In Date
          </label>
          <input type="date" id="check-in-date" className="w-full p-3 rounded-xl bg-gray-100 border-none focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div className="mt-4">
          <label htmlFor="guest-count" className="block text-lg font-bold text-blue-600 mb-2">
            Guest Count
          </label>
          <input type="number" id="guest-count" placeholder="Guests" className="w-full p-3 rounded-xl bg-gray-100 border-none focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <button className="mt-4 px-6 py-3 text-white font-bold bg-blue-600 hover:bg-blue-700 rounded-xl">
          Apply Filters
        </button>
      </div>

      {/* Table Section */}
      <table className="w-full border-collapse shadow-md">
        <thead className="bg-blue-500 text-white">
          <tr>
            <th className="p-4">Booking ID</th>
            <th className="p-4">Guest Name</th>
            <th className="p-4">Room Type</th>
            <th className="p-4">Check-In Date</th>
            <th className="p-4">Total Price</th>
            <th className="p-4 text-center">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="p-4">1001</td>
            <td className="p-4">John Doe</td>
            <td className="p-4">Deluxe Room</td>
            <td className="p-4">2023-10-05</td>
            <td className="p-4">$299.99</td>
            <td className="p-4 text-center">
              <button className="px-6 py-2 text-white font-bold bg-blue-600 hover:bg-blue-700 rounded-xl">View Details</button>
              <button className="ml-3 px-6 py-2 text-white font-bold bg-red-500 hover:bg-red-600 rounded-xl">Cancel Booking</button>
            </td>
          </tr>
        </tbody>
      </table>

      {/* Pagination Section */}
      <div className="mt-8 flex justify-center">
        <nav aria-label="Pagination" className="flex items-center space-x-4">
          <a href="#" className="px-6 py-3 text-blue-500 font-bold bg-white hover:bg-gray-100 rounded-xl border border-blue-500">Previous</a>
          <span>...</span>
          <a href="#" className="px-6 py-3 text-blue-500 font-bold bg-white hover:bg-gray-100 rounded-xl border border-blue-500">2</a>
          <button className="px-6 py-3 text-white font-bold bg-blue-600 hover:bg-blue-700 rounded-xl">3</button>
          <a href="#" className="px-6 py-3 text-blue-500 font-bold bg-white hover:bg-gray-100 rounded-xl border border-blue-500">4</a>
          <span>...</span>
          <a href="#" className="px-6 py-3 text-blue-500 font-bold bg-white hover:bg-gray-100 rounded-xl border border-blue-500">Next</a>
        </nav>
      </div>
    </div>
  );
};

export default TablePage2;