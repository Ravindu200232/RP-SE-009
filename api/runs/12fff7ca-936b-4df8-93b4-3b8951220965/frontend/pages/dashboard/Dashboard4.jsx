import React from "react";

const Dashboard4 = () => {
  return (
    <div className="bg-white min-h-screen p-8">
      <header className="mb-10">
        <h1 className="text-3xl font-bold mb-2">Welcome to BookStay</h1>
        <p className="text-gray-600">Manage your listings, calendars and bookings.</p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-black p-4 rounded-md shadow-[4px_4px_0_#000]">
          <h2 className="text-xl font-bold text-white">Total Bookings</h2>
          <p className="text-3xl font-extrabold mt-1 text-primary-500">#9876</p>
        </div>

        <div className="bg-black p-4 rounded-md shadow-[4px_4px_0_#000]">
          <h2 className="text-xl font-bold text-white">Total Revenue</h2>
          <p className="text-3xl font-extrabold mt-1 text-primary-500">$7,890.00</p>
        </div>

        <div className="bg-black p-4 rounded-md shadow-[4px_4px_0_#000]">
          <h2 className="text-xl font-bold text-white">Average Rating</h2>
          <p className="text-3xl font-extrabold mt-1 text-primary-500">4.7/5</p>
        </div>

        <div className="bg-black p-4 rounded-md shadow-[4px_4px_0_#000]">
          <h2 className="text-xl font-bold text-white">Active Listings</h2>
          <p className="text-3xl font-extrabold mt-1 text-primary-500">#654</p>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-bold mb-4">Recent Activity</h2>
        <ul className="divide-y divide-gray-300">
          <li className="py-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-black">Booking Confirmed</p>
              <p className="text-sm text-gray-600">John Doe booked Room 123 for next week.</p>
            </div>
            <time className="text-sm text-gray-500">Yesterday, 4:30 PM</time>
          </li>
          <li className="py-4 flex items-center justify-between">
            <div>
              <p className="font-semibold text-black">Review Posted</p>
              <p className="text-sm text-gray-600">Jane Smith left a 5-star review for Room 123.</p>
            </div>
            <time className="text-sm text-gray-500">Today, 9:15 AM</time>
          </li>
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-bold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <button className="bg-black text-white p-4 rounded-md shadow-[4px_4px_0_#000] flex items-center justify-center w-full h-28">
            View Bookings
          </button>
          <button className="bg-black text-white p-4 rounded-md shadow-[4px_4px_0_#000] flex items-center justify-center w-full h-28">
            Add New Listing
          </button>
          <button className="bg-black text-white p-4 rounded-md shadow-[4px_4px_0_#000] flex items-center justify-center w-full h-28">
            Edit Profile
          </button>
        </div>
      </section>

      <footer className="mt-16 border-t pt-8">
        <p className="text-sm text-gray-500">© 2023 Acme Travel Co. All rights reserved.</p>
      </footer>
    </div>
  );
};

export default Dashboard4;