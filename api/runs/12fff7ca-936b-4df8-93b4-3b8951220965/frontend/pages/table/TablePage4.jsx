import React from "react";

const TablePage4 = () => {
  return (
    <div className="p-8">
      <h1 className="text-4xl font-bold mb-4">Bookings</h1>
      <div className="flex justify-between items-center mb-6">
        <form className="w-full md:w-auto flex space-x-2">
          <input
            type="search"
            placeholder="Search bookings..."
            className="border border-black p-2 rounded-md w-full sm:w-auto"
          />
          <button type="submit" className="bg-blue-500 text-white px-4 py-2 rounded-md">
            Search
          </button>
        </form>
      </div>

      <table className="w-full border-collapse mb-8">
        <thead className="border-b border-black bg-gray-100">
          <tr>
            <th className="p-3 text-left">Booking ID</th>
            <th className="p-3 text-left">Guest Name</th>
            <th className="p-3 text-left">Check-in Date</th>
            <th className="p-3 text-left">Room Type</th>
            <th className="p-3 text-left">Total Cost</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-black">
            <td className="p-3">1234567890</td>
            <td className="p-3">John Doe</td>
            <td className="p-3">2023-10-01</td>
            <td className="p-3">Deluxe Room</td>
            <td className="p-3">$150.00</td>
            <td className="p-3 flex items-center space-x-2">
              <button className="bg-blue-500 text-white px-4 py-2 rounded-md shadow-[4px_4px_0_#000]">View</button>
              <button className="bg-red-500 text-white px-4 py-2 rounded-md shadow-[4px_4px_0_#000]">Cancel</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div className="flex justify-between items-center">
        <p>Showing 1-10 of 50 bookings</p>
        <nav aria-label="Page navigation" className="flex space-x-2">
          <button className="border border-black p-2 rounded-md shadow-[4px_4px_0_#000]">Previous</button>
          <span>...</span>
          <button className="border border-black p-2 rounded-md shadow-[4px_4px_0_#000]">Next</button>
        </nav>
      </div>
    </div>
  );
};

export default TablePage4;