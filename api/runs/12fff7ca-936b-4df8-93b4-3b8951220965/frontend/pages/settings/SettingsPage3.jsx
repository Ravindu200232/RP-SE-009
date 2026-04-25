import React from "react";

const SettingsPage3 = () => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-blue-100 to-cyan-200">
      <div className="p-8 backdrop-blur-md rounded-lg bg-white/30 shadow-xl max-w-4xl w-full mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-primary">Account Settings</h1>
        <section id="profile" className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">Profile Information</h2>
          <form className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="relative">
                <input type="text" id="name" name="name" placeholder="Name" className="block w-full px-3 py-2 border rounded-lg focus:border-primary focus:ring-primary bg-transparent" />
              </div>
              <div className="relative">
                <input type="email" id="email" name="email" placeholder="Email Address" className="block w-full px-3 py-2 border rounded-lg focus:border-primary focus:ring-primary bg-transparent" />
              </div>
            </div>
            <button type="submit" className="w-full bg-primary text-white font-semibold py-2 rounded-lg hover:bg-primary/80">
              Save Changes
            </button>
          </form>
        </section>
        <hr className="my-6 border-gray-300" />
        <section id="security" className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">Security</h2>
          <div className="space-y-4">
            <button type="submit" className="w-full bg-primary text-white font-semibold py-2 rounded-lg hover:bg-primary/80">
              Change Password
            </button>
            <button type="submit" className="w-full bg-red-500 text-white font-semibold py-2 rounded-lg hover:bg-red-600">
              Delete Account
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};

export default SettingsPage3;