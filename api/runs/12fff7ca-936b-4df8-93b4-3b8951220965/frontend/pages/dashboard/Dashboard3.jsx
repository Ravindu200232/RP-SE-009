import React from "react";

const Dashboard3 = () => {
  return (
    <div className="bg-white/30 backdrop-blur-sm p-8 rounded-lg shadow-md max-w-screen-xl mx-auto">
      <header className="mb-6 text-center">
        <h1 className="text-2xl font-bold">BookStay</h1>
        <p className="mt-1 text-gray-500">Find your next stay in seconds.</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Stats Section */}
        <div className="bg-white/20 backdrop-blur-sm p-4 rounded-lg shadow-md flex items-center justify-between text-gray-900">
          <div>
            <p className="text-xl font-semibold">5</p>
            <span className="block mt-1 text-sm">Active Bookings</span>
          </div>
          <div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
              <path fill="#2563eb" d="M17.985 13a1 1 0 0 0-1.414-.293l-4.586 4.586A1 1 0 0 0 14 17h-2v-2H8c-.55 0-1-.45-1-1V7c0-.55.45-1 1-1h3V4a1 1 0 0 0-2 0v1H6A2 2 0 0 0 4 8v8a2 2 0 0 0 2 2h12c.55 0 1-.45 1-1V9c0-.55-.45-1-1-1zm7-3H6l-1.5 1.5L8.5 12l1.5 1.5L16 10h2v-2z" />
            </svg>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white/20 backdrop-blur-sm p-4 rounded-lg shadow-md">
          <header className="flex justify-between items-center mb-3">
            <span className="text-gray-900">Recent Activity</span>
            <button className="text-blue-500 hover:text-blue-700 focus:outline-none">View All</button>
          </header>

          {/* Recent Activity Items */}
          <div className="space-y-3">
            <p className="flex items-center text-gray-900">
              <span>New booking for room 123 on March 15th.</span>
            </p>
            <p className="flex items-center text-gray-900">
              <span>Updated pricing and availability for April.</span>
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white/20 backdrop-blur-sm p-4 rounded-lg shadow-md flex flex-col space-y-3 text-gray-900">
          <button className="text-blue-500 hover:text-blue-700 focus:outline-none">View Bookings</button>
          <button className="text-blue-500 hover:text-blue-700 focus:outline-none">Add New Room</button>
          <button className="text-blue-500 hover:text-blue-700 focus:outline-none">Manage Reviews</button>
        </div>
      </div>

      {/* Features Section */}
      <section className="mt-8">
        <h2 className="mb-4 text-xl font-bold">Features</h2>
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            "Search Rooms",
            "Room Details",
            "Secure Checkout",
            "Host Dashboard",
            "Reviews"
          ].map((feature) => (
            <li key={feature} className="bg-white/20 backdrop-blur-sm p-4 rounded-lg shadow-md flex items-center justify-between text-gray-900">
              <span>{feature}</span>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                <path fill="#2563eb" d="M17.985 13a1 1 0 0 0-1.414-.293l-4.586 4.586A1 1 0 0 0 14 17h-2v-2H8c-.55 0-1-.45-1-1V7c0-.55.45-1 1-1h3V4a1 1 0 0 0-2 0v1H6A2 2 0 0 0 4 8v8a2 2 0 0 0 2 2h12c.55 0 1-.45 1-1V9c0-.55-.45-1-1-1zm7-3H6l-1.5 1.5L8.5 12l1.5 1.5L16 10h2v-2z" />
              </svg>
            </li>
          ))}
        </ul>
      </section>

    </div>
  );
};

export default Dashboard3;