import React from "react";

const SettingsPage4 = () => {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">Account Settings</h1>
      <section className="mb-6 shadow-[4px_4px_0_#000] p-4 rounded-md bg-white">
        <h2 className="text-xl font-semibold mb-2">Profile Information</h2>
        <div className="space-y-3">
          <label htmlFor="username" className="block text-sm font-medium">
            Username
          </label>
          <input
            type="text"
            id="username"
            className="border border-black p-2 rounded-md w-full"
            placeholder="Username"
          />
        </div>

        <div className="space-y-3 mt-4">
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            type="text"
            id="email"
            className="border border-black p-2 rounded-md w-full"
            placeholder="Email address"
          />
        </div>

        <div className="space-y-3 mt-4">
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            type="password"
            id="password"
            className="border border-black p-2 rounded-md w-full"
            placeholder="Password"
          />
        </div>

        <button className="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md">
          Save Changes
        </button>
      </section>

      <section className="mb-6 shadow-[4px_4px_0_#000] p-4 rounded-md bg-white mt-8">
        <h2 className="text-xl font-semibold mb-2">Notifications</h2>
        <div className="flex items-center space-x-3">
          <input
            type="checkbox"
            id="email-notifications"
            className="border-black"
          />
          <label htmlFor="email-notifications" className="block text-sm">
            Email Notifications
          </label>
        </div>

        <div className="flex items-center mt-4 space-x-3">
          <input
            type="checkbox"
            id="sms-notifications"
            className="border-black"
          />
          <label htmlFor="sms-notifications" className="block text-sm">
            SMS Notifications
          </label>
        </div>

        <button className="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md">
          Save Changes
        </button>
      </section>

      <section className="shadow-[4px_4px_0_#000] p-4 rounded-md bg-white mt-8">
        <h2 className="text-xl font-semibold mb-2">Security</h2>
        <div className="space-y-3">
          <label htmlFor="two-factor" className="block text-sm font-medium">
            Two-Factor Authentication
          </label>
          <input
            type="checkbox"
            id="two-factor"
            className="border-black"
          />
        </div>

        <button className="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md">
          Save Changes
        </button>
      </section>
    </div>
  );
};

export default SettingsPage4;