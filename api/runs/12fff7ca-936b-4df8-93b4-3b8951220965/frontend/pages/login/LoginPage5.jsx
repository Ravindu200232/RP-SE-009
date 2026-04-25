import React from "react";

const LoginPage5 = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
        <h2 className="text-xl font-bold mb-6 text-blue-700">Sign In</h2>
        <form action="#" method="POST" className="space-y-4">
          <label htmlFor="email" className="block text-gray-700">
            Email
          </label>
          <input
            type="text"
            id="email"
            name="email"
            placeholder="you@example.com"
            className="w-full p-2 border rounded-md focus:outline-none focus:border-blue-500"
          />
          <label htmlFor="password" className="block text-gray-700">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            placeholder="••••••••"
            className="w-full p-2 border rounded-md focus:outline-none focus:border-blue-500"
          />
          <div className="flex items-center justify-between">
            <button
              type="submit"
              className="bg-blue-700 text-white px-4 py-2 rounded-md hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Sign In
            </button>
            <a href="#" className="text-sm text-gray-600">
              Forgot password?
            </a>
          </div>
        </form>
        <hr className="my-4 border-gray-300" />
        <h2 className="text-lg font-semibold mb-2">Sign In with</h2>
        <ul className="flex items-center justify-between space-x-4">
          <li>
            <a href="#" className="bg-white text-blue-700 px-4 py-2 rounded-md hover:bg-gray-100 flex items-center space-x-2">
              <img src="/path/to/facebook-icon.svg" alt="Facebook" />
              Facebook
            </a>
          </li>
          <li>
            <a href="#" className="bg-white text-blue-700 px-4 py-2 rounded-md hover:bg-gray-100 flex items-center space-x-2">
              <img src="/path/to/google-icon.svg" alt="Google" />
              Google
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default LoginPage5;