import React from "react";

const SettingsPage1 = () => {
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <h1 className="text-xl font-bold mb-2">Account Settings</h1>
      <hr className="my-4 border-gray-300" />
      
      {/* Profile Section */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Profile Information</h2>
        <form>
          <div className="flex flex-col space-y-2">
            <label htmlFor="username" className="block text-sm font-medium text-gray-700">
              Username
            </label>
            <input type="text" id="username" className="border border-gray-300 rounded p-1 focus:ring-2 focus:ring-blue-500" />
            
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input type="text" id="email" className="border border-gray-300 rounded p-1 focus:ring-2 focus:ring-blue-500" />
            
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input type="password" id="password" className="border border-gray-300 rounded p-1 focus:ring-2 focus:ring-blue-500" />
            
            <button type="submit" className="mt-4 bg-blue-500 text-white py-2 px-4 rounded hover:bg-blue-600">
              Save Changes
            </button>
          </div>
        </form>
      </section>

      {/* Notifications Section */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Notifications</h2>
        <p className="text-sm text-gray-500 mb-4">Choose which notifications you'd like to receive.</p>
        
        <div className="flex flex-col space-y-1">
          <label htmlFor="bookingRequest" className="block text-sm font-medium text-gray-700 cursor-pointer">
            Booking Request
            <input type="checkbox" id="bookingRequest" className="ml-2 mr-1" />
          </label>
          
          <label htmlFor="paymentConfirmation" className="block text-sm font-medium text-gray-700 cursor-pointer">
            Payment Confirmation
            <input type="checkbox" id="paymentConfirmation" className="ml-2 mr-1" />
          </label>
        </div>
      </section>

      {/* Security Section */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-2">Security</h2>
        
        <p className="text-sm text-gray-500 mb-4">Keep your account secure with two-factor authentication.</p>
        
        <div className="flex items-center space-x-1">
          <label htmlFor="twoFactor" className="block text-sm font-medium text-gray-700 cursor-pointer">
            Two-Factor Authentication
            <input type="checkbox" id="twoFactor" className="ml-2 mr-1" />
          </label>
        </div>
      </section>

    </div>
  );
};

export default SettingsPage1;