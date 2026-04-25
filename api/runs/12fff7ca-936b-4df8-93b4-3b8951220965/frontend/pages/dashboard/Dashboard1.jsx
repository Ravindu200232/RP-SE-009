import React from "react";

const Dashboard1 = () => {
  return (
    <div className="max-w-7xl mx-auto p-4">
      {/* Header Section */}
      <header className="mb-8 flex justify-between items-center">
        <h1 className="text-xl font-bold">Host Dashboard</h1>
        <nav className="flex space-x-4 text-sm text-gray-600">
          {["Discover", "My Trips", "Hosting", "Inbox", "Account"].map(
            (item, index) => (
              <span key={index} className="hover:underline cursor-pointer">
                {item}
              </span>
            )
          )}
        </nav>
      </header>

      {/* Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div className="p-6 border rounded bg-white shadow-sm hover:bg-gray-50 transition duration-150 ease-in-out">
          <h2 className="text-lg font-medium">Listings</h2>
          <span className="block mt-2 text-xl font-bold">3</span>
        </div>
        <div className="p-6 border rounded bg-white shadow-sm hover:bg-gray-50 transition duration-150 ease-in-out">
          <h2 className="text-lg font-medium">Bookings</h2>
          <span className="block mt-2 text-xl font-bold">7</span>
        </div>
        <div className="p-6 border rounded bg-white shadow-sm hover:bg-gray-50 transition duration-150 ease-in-out">
          <h2 className="text-lg font-medium">Reviews</h2>
          <span className="block mt-2 text-xl font-bold">4.8</span>
        </div>
      </div>

      {/* Recent Activity Section */}
      <section className="mb-8 border rounded bg-white shadow-sm p-6">
        <header className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">Recent Activity</h3>
          <span className="text-gray-500 text-xs">View all</span>
        </header>
        <ul className="space-y-2">
          <li className="border-b pb-2 last:border-none">
            <p className="text-sm text-gray-600">New booking for Room 104</p>
            <time className="block mt-1 text-xs text-gray-500">Today, 9:30 AM</time>
          </li>
          <li className="border-b pb-2 last:border-none">
            <p className="text-sm text-gray-600">Review posted for Room 104</p>
            <time className="block mt-1 text-xs text-gray-500">Yesterday, 3:15 PM</time>
          </li>
        </ul>
      </section>

      {/* Quick Actions Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button className="p-6 border rounded bg-white shadow-sm hover:bg-gray-50 transition duration-150 ease-in-out flex items-center justify-between w-full text-left">
          <span>
            <h3 className="text-lg font-medium">Add New Listing</h3>
            <p className="mt-2 text-sm text-gray-600">Create a new room listing</p>
          </span>
        </button>
        <button className="p-6 border rounded bg-white shadow-sm hover:bg-gray-50 transition duration-150 ease-in-out flex items-center justify-between w-full text-left">
          <span>
            <h3 className="text-lg font-medium">Manage Calendar</h3>
            <p className="mt-2 text-sm text-gray-600">Update room availability</p>
          </span>
        </button>
      </div>
    </div>
  );
};

export default Dashboard1;