import React from "react";

const LoginPage2 = () => {
  return (
    <div className="flex min-h-screen bg-gradient-to-br from-blue-400 to-purple-700">
      <div className="m-auto max-w-md p-10 rounded-2xl shadow-lg bg-white">
        <h1 className="text-3xl font-bold text-center mb-6">BookStay</h1>
        <p className="text-xl text-center mb-8">{SRS.brand.tagline}</p>

        {/* Form */}
        <form className="space-y-4">
          <div className="relative">
            <input
              type="email"
              placeholder="Email address"
              className="w-full p-3 rounded-lg border-none focus:ring-2 focus:ring-blue-500"
            />
            <label htmlFor="email" className="absolute top-1 left-4 text-gray-600">
              Email
            </label>
          </div>

          <div className="relative">
            <input
              type="password"
              placeholder="Password"
              className="w-full p-3 rounded-lg border-none focus:ring-2 focus:ring-blue-500"
            />
            <label htmlFor="password" className="absolute top-1 left-4 text-gray-600">
              Password
            </label>
          </div>

          <button type="submit" className="w-full p-3 rounded-lg bg-blue-500 text-white font-bold hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400">
            Sign In
          </button>

          <p className="text-center mt-4 mb-6">
            Don't have an account?{" "}
            <a href="#" className="underline text-blue-500 hover:text-blue-700">
              Register here
            </a>
          </p>
        </form>

        {/* Social Login */}
        <div className="flex justify-center space-x-4 mb-6">
          <button className="w-full p-3 rounded-lg bg-white text-gray-800 border border-blue-500 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
            Sign In with Google
          </button>
          <button className="w-full p-3 rounded-lg bg-white text-gray-800 border border-blue-500 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-400">
            Sign In with Facebook
          </button>
        </div>

        {/* Branding Panel */}
        <div className="flex justify-center space-x-4 mb-6">
          <img src="/logo.png" alt="BookStay Logo" className="w-12 h-12 rounded-full border-2 border-blue-500 p-1" />
          <p className="text-xl font-bold text-gray-800">Powered by BookStay</p>
        </div>

        {/* Navigation Links */}
        <nav className="flex justify-center space-x-4 mb-6">
          {SRS.navigation.map((item, index) => (
            <a key={index} href="#" className="text-blue-500 hover:text-blue-700 focus:outline-none focus:underline">
              {item}
            </a>
          ))}
        </nav>

        {/* Footer */}
        <div className="flex justify-center text-sm text-gray-600 mb-4">
          &copy; 2023 Acme Travel Co. All rights reserved.
        </div>
      </div>
    </div>
  );
};

export default LoginPage2;