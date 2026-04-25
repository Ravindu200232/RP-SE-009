import React from "react";

const Dashboard2 = () => {
  return (
    <div className="bg-white shadow-lg rounded-2xl p-8">
      <header>
        <h1 className="text-3xl font-bold text-blue-500">BookStay</h1>
        <p className="mt-2 text-xl font-semibold text-gray-700">Find your next stay in seconds.</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-6">
        <div className="bg-blue-500 rounded-2xl p-4 flex items-center justify-between text-white shadow-md">
          <div>
            <h2 className="text-xl font-bold">Total Bookings</h2>
            <p className="mt-1 text-lg font-semibold">378</p>
          </div>
          <span className="material-icons text-4xl">calendar_today</span>
        </div>

        <div className="bg-yellow-500 rounded-2xl p-4 flex items-center justify-between text-white shadow-md">
          <div>
            <h2 className="text-xl font-bold">Upcoming Trips</h2>
            <p className="mt-1 text-lg font-semibold">8</p>
          </div>
          <span className="material-icons text-4xl">flight_takeoff</span>
        </div>

        <div className="bg-green-500 rounded-2xl p-4 flex items-center justify-between text-white shadow-md">
          <div>
            <h2 className="text-xl font-bold">Guest Reviews</h2>
            <p className="mt-1 text-lg font-semibold">97%</p>
          </div>
          <span className="material-icons text-4xl">star_rate</span>
        </div>

        <div className="col-span-3">
          <table className="w-full bg-blue-50 rounded-2xl shadow-md p-6">
            <thead>
              <tr>
                <th className="text-left font-bold text-white bg-blue-700 py-4">Booking ID</th>
                <th className="text-left font-bold text-white bg-blue-700 py-4">Guest Name</th>
                <th className="text-left font-bold text-white bg-blue-700 py-4">Check-in Date</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-2 px-4">123456</td>
                <td className="py-2 px-4">John Doe</td>
                <td className="py-2 px-4">2023-10-01</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="col-span-3">
          <form action="#" method="POST" className="bg-blue-50 rounded-2xl shadow-md p-6">
            <h2 className="text-xl font-bold text-blue-700 mb-4">Quick Actions</h2>
            <div className="mb-4">
              <label htmlFor="search_rooms" className="block text-gray-700 font-semibold mb-1">Search Rooms</label>
              <input type="text" id="search_rooms" name="search_rooms" placeholder="Enter city or dates" className="w-full p-2 rounded-xl bg-white border-blue-500 focus:outline-none focus:border-blue-600"/>
            </div>

            <button type="submit" className="bg-blue-700 text-white font-bold py-2 px-4 rounded-xl hover:bg-blue-800">
              Search
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Dashboard2;