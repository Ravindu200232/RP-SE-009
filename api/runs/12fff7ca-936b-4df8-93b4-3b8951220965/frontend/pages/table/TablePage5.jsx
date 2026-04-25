import React from "react";

const TablePage5 = () => {
  return (
    <div className="bg-gray-100 min-h-screen p-4">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-blue-700">BookStay</h1>
        <nav className="space-x-2">
          <a href="#" className="text-gray-500 hover:text-blue-700">Discover Stays</a>
          <a href="#" className="text-gray-500 hover:text-blue-700">My Trips</a>
          <a href="#" className="text-gray-500 hover:text-blue-700">Hosting</a>
          <a href="#" className="text-gray-500 hover:text-blue-700">Inbox</a>
          <a href="#" className="text-gray-500 hover:text-blue-700">Account Settings</a>
        </nav>
      </header>

      <div className="bg-white rounded-lg shadow-md p-4">
        <h2 className="text-xl font-bold mb-4 text-blue-700">Bookings</h2>
        <form className="mb-6">
          <div className="flex items-center space-x-3">
            <label htmlFor="search" className="block text-gray-500">Search:</label>
            <input type="text" id="search" placeholder="Search bookings..." className="border p-2 rounded-lg w-full" />
          </div>
        </form>

        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="p-3 text-left font-semibold bg-gray-100">Booking ID</th>
              <th className="p-3 text-left font-semibold bg-gray-100">Guest Name</th>
              <th className="p-3 text-left font-semibold bg-gray-100">Check-in Date</th>
              <th className="p-3 text-left font-semibold bg-gray-100">Check-out Date</th>
              <th className="p-3 text-left font-semibold bg-gray-100">Room Type</th>
              <th className="p-3 text-left font-semibold bg-gray-100">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-3 border-t">123456789</td>
              <td className="p-3 border-t">John Doe</td>
              <td className="p-3 border-t">2023-10-01</td>
              <td className="p-3 border-t">2023-10-07</td>
              <td className="p-3 border-t">Deluxe Room</td>
              <td className="p-3 border-t">
                <button className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">View Details</button>
                <button className="ml-2 bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600">Cancel Booking</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div className="flex justify-between items-center mt-4">
          <nav aria-label="Page navigation" className="space-x-3">
            <a href="#" className="text-gray-500 hover:text-blue-700">Previous</a>
            <a href="#" className="text-gray-500 hover:text-blue-700">Next</a>
          </nav>
        </div>
      </div>
    </div>
  );
};

export default TablePage5;