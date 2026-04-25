import React from "react";

const Dashboard5 = () => {
  return (
    <div className="bg-gray-100 min-h-screen p-8">
      <header className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-blue-700">BookStay</h1>
        <nav className="space-x-4">
          {["Discover", "My Trips", "Hosting", "Inbox", "Account"].map((item, index) => (
            <a key={index} href="#" className="text-gray-600 hover:text-blue-700 transition-colors">
              {item}
            </a>
          ))}
        </nav>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Total Bookings</span>
            <h2 className="text-xl font-semibold">154</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M7.91 12l-.78-.78c-.39-.39-.39-1.02 0-1.41.39-.39 1.02-.39 1.41 0L12 10.59l4.41 4.41c.39.39.39 1.02 0 1.41-.39.39-1.02.39-1.41 0L12 13.41 7.59 9.91z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Active Listings</span>
            <h2 className="text-xl font-semibold">34</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M19.75 4H4.25A2.25 2.25 0 002 6.25v11.5a2.25 2.25 0 002.25 2.25h11.5a2.25 2.25 0 002.25-2.25V6.25A2.25 2.25 0 0019.75 4zm-.75 3c-.41 0-.75.34-.75.75v8.5c0 .41.34.75.75.75s.75-.34.75-.75V7.75C20.5 6.34 19.89 5 19.06 5z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Average Rating</span>
            <h2 className="text-xl font-semibold">4.8/5</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14l3-4-3-4v6h6V9H9V5a1 1 0 012-1h2a1 1 0 011 1v10a1 1 0 01-1 1h-2zm8.72-.2l-3 4 3 4v-6c0-1.1-.9-2-2-2H9V15h6v-2z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Total Reviews</span>
            <h2 className="text-xl font-semibold">154</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M19.75 4H4.25A2.25 2.25 0 002 6.25v11.5a2.25 2.25 0 002.25 2.25h11.5a2.25 2.25 0 002.25-2.25V6.25A2.25 2.25 0 0019.75 4zm-.75 3c-.41 0-.75.34-.75.75v8.5c0 .41.34.75.75.75s.75-.34.75-.75V7.75C20.5 6.34 19.89 5 19.06 5z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Total Earnings</span>
            <h2 className="text-xl font-semibold">$15,432.98</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M17.99 13H14v-2h3.99c-.17 1.28-.85 2.37-1.99 2.37-1.14 0-1.76-.92-1.99-2zm-1.99 2H14V13h3.99c.17-1.28.85-2.37 1.99-2.37 1.14 0 1.76.92 1.99 2zM12 16a4 4 0 110-8 4 4 0 010 8zm-1-5h2v2h-2V11z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Upcoming Bookings</span>
            <h2 className="text-xl font-semibold">15</h2>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-8 h-8">
            <path d="M19.75 4H4.25A2.25 2.25 0 002 6.25v11.5a2.25 2.25 0 002.25 2.25h11.5a2.25 2.25 0 002.25-2.25V6.25A2.25 2.25 0 0019.75 4zm-.75 3c-.41 0-.75.34-.75.75v8.5c0 .41.34.75.75.75s.75-.34.75-.75V7.75C20.5 6.34 19.89 5 19.06 5z" />
          </svg>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Recent Activity</span>
            <ul role="list" className="mt-4 space-y-3">
              <li className="flex items-center gap-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-5 h-5">
                  <path d="M17.99 13H14v-2h3.99c-.17 1.28-.85 2.37-1.99 2.37-1.14 0-1.76-.92-1.99-2zm-1.99 2H14V13h3.99c.17-1.28.85-2.37 1.99-2.37 1.14 0 1.76.92 1.99 2zM12 16a4 4 0 110-8 4 4 0 010 8zm-1-5h2v2h-2V11z" />
                </svg>
                <div className="text-sm">
                  <p className="font-semibold text-gray-900">New Booking</p>
                  <p className="text-gray-600">John Doe booked your room for the weekend.</p>
                </div>
              </li>
              <li className="flex items-center gap-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-5 h-5">
                  <path d="M17.99 13H14v-2h3.99c-.17 1.28-.85 2.37-1.99 2.37-1.14 0-1.76-.92-1.99-2zm-1.99 2H14V13h3.99c.17-1.28.85-2.37 1.99-2.37 1.14 0 1.76.92 1.99 2zM12 16a4 4 0 110-8 4 4 0 010 8zm-1-5h2v2h-2V11z" />
                </svg>
                <div className="text-sm">
                  <p className="font-semibold text-gray-900">Review Posted</p>
                  <p className="text-gray-600">Jane Smith left a 5-star review for your room.</p>
                </div>
              </li>
            </ul>
          </div>
        </section>

        <section className="bg-white p-6 shadow-md rounded-lg flex items-center justify-between">
          <div className="flex flex-col text-gray-700">
            <span className="text-sm font-bold">Quick Actions</span>
            <ul role="list" className="mt-4 space-y-3">
              <li className="flex items-center gap-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-5 h-5">
                  <path d="M17.99 13H14v-2h3.99c-.17 1.28-.85 2.37-1.99 2.37-1.14 0-1.76-.92-1.99-2zm-1.99 2H14V13h3.99c.17-1.28.85-2.37 1.99-2.37 1.14 0 1.76.92 1.99 2zM12 16a4 4 0 110-8 4 4 0 010 8zm-1-5h2v2h-2V11z" />
                </svg>
                <div className="text-sm">
                  <p className="font-semibold text-gray-900">View Bookings</p>
                  <p className="text-gray-600">Check your upcoming and past bookings.</p>
                </div>
              </li>
              <li className="flex items-center gap-x-3">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#2563eb" className="w-5 h-5">
                  <path d="M17.99 13H14v-2h3.99c-.17 1.28-.85 2.37-1.99 2.37-1.14 0-1.76-.92-1.99-2zm-1.99 2H14V13h3.99c.17-1.28.85-2.37 1.99-2.37 1.14 0 1.76.92 1.99 2zM12 16a4 4 0 110-8 4 4 0 010 8zm-1-5h2v2h-2V11z" />
                </svg>
                <div className="text-sm">
                  <p className="font-semibold text-gray-900">Manage Listings</p>
                  <p className="text-gray-600">Edit or add new listings for your rooms.</p>
                </div>
              </li>
            </ul>
          </div>
        </section>

      </div>
    </div>
  );
};

export default Dashboard5;