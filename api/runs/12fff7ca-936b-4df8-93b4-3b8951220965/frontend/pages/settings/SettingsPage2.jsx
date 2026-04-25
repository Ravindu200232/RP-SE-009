import React from "react";

const SettingsPage2 = () => {
  return (
    <div className="bg-white rounded-2xl shadow-lg p-8">
      <h1 className="text-3xl font-bold text-blue-600 mb-4">Account Settings</h1>
      <form className="space-y-6">
        <section className="rounded-2xl bg-blue-50 p-6 mb-4">
          <div className="mb-4">
            <label htmlFor="username" className="block text-sm font-medium text-gray-700">Username</label>
            <input type="text" id="username" name="username" className="mt-1 block w-full rounded-md border-blue-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" placeholder="Your username"/>
          </div>
          <div className="mb-4">
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">Email</label>
            <input type="text" id="email" name="email" className="mt-1 block w-full rounded-md border-blue-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" placeholder="Your email"/>
          </div>
          <button type="submit" className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
            Save Changes
          </button>
        </section>

        <section className="rounded-2xl bg-blue-50 p-6 mb-4">
          <h2 className="text-xl font-bold text-blue-800">Security</h2>
          <div className="mt-4 flex items-center space-x-3">
            <input id="twoFactorAuth" type="checkbox" className="focus:ring-indigo-500 h-4 w-4 rounded border-gray-300"/>
            <label htmlFor="twoFactorAuth" className="block text-sm font-medium text-gray-700">Enable Two-Factor Authentication</label>
          </div>

          <h2 className="text-xl font-bold text-blue-800 mt-6">Notifications</h2>
          <div className="mt-4 flex items-center space-x-3">
            <input id="emailNotifications" type="checkbox" className="focus:ring-indigo-500 h-4 w-4 rounded border-gray-300"/>
            <label htmlFor="emailNotifications" className="block text-sm font-medium text-gray-700">Email Notifications</label>
          </div>

          <button type="submit" className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4">
            Save Changes
          </button>
        </section>

        <section className="rounded-2xl bg-blue-50 p-6 mb-4">
          <h2 className="text-xl font-bold text-blue-800">Payment Information</h2>
          <div className="mt-4 flex items-center space-x-3">
            <input id="paymentMethod" type="checkbox" className="focus:ring-indigo-500 h-4 w-4 rounded border-gray-300"/>
            <label htmlFor="paymentMethod" className="block text-sm font-medium text-gray-700">Update Payment Method</label>
          </div>

          <button type="submit" className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4">
            Save Changes
          </button>
        </section>

      </form>
    </div>
  );
};

export default SettingsPage2;