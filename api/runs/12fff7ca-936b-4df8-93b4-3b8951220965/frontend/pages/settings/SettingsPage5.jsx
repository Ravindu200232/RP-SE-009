import React from "react";

const SettingsPage5 = () => {
  return (
    <div className="bg-gray-100 min-h-screen p-8">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold text-blue-700">Account Settings</h1>
        <button className="rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 focus:outline-none">
          Save Changes
        </button>
      </header>

      <section className="mb-8 rounded-lg border border-gray-300 p-6 shadow-md">
        <h2 className="text-lg font-semibold">Profile Information</h2>
        <form className="mt-4 grid gap-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label htmlFor="firstName" className="block">
              First Name
              <input
                type="text"
                id="firstName"
                name="firstName"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </label>
            <label htmlFor="lastName" className="block">
              Last Name
              <input
                type="text"
                id="lastName"
                name="lastName"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </label>
          </div>

          <label htmlFor="email" className="block">
            Email Address
            <input
              type="email"
              id="email"
              name="email"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </label>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label htmlFor="phone" className="block">
              Phone Number
              <input
                type="tel"
                id="phone"
                name="phone"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </label>
            <label htmlFor="password" className="block">
              Password
              <input
                type="password"
                id="password"
                name="password"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </label>
          </div>

          <button
            type="submit"
            className="rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 focus:outline-none"
          >
            Update Profile Information
          </button>
        </form>
      </section>

      <section className="mb-8 rounded-lg border border-gray-300 p-6 shadow-md">
        <h2 className="text-lg font-semibold">Notification Preferences</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label htmlFor="emailNotifications" className="block flex items-center space-x-2">
            Email Notifications
            <input type="checkbox" id="emailNotifications" name="emailNotifications" />
          </label>

          <label htmlFor="smsNotifications" className="block flex items-center space-x-2">
            SMS Notifications
            <input type="checkbox" id="smsNotifications" name="smsNotifications" />
          </label>
        </div>
      </section>

      <footer className="mt-8 text-sm text-gray-500">
        © {new Date().getFullYear()} BookStay. All rights reserved.
      </footer>
    </div>
  );
};

export default SettingsPage5;