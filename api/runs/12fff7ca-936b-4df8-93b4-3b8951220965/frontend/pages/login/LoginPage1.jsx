import React from "react";

const LoginPage1 = () => {
  return (
    <div className="flex h-screen bg-white">
      {/* Branding Panel */}
      <div className="w-2/5 flex items-center justify-center border-r px-8 py-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">BookStay</h1>
          <p className="mt-2 text-sm text-gray-600">Find your next stay in seconds.</p>
        </div>
      </div>

      {/* Login Form Panel */}
      <div className="w-3/5 flex items-center justify-center">
        <form className="max-w-md w-full p-8 bg-white border rounded-lg shadow-md">
          <h2 className="text-xl font-bold mb-4 text-gray-900">Sign In</h2>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            type="email"
            id="email"
            name="email"
            className="w-full p-2 border rounded-md focus:outline-none focus:border-blue-500 mb-4"
            placeholder="Enter your email address"
          />
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            className="w-full p-2 border rounded-md focus:outline-none focus:border-blue-500 mb-4"
            placeholder="Enter your password"
          />
          <button
            type="submit"
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 transition duration-300"
          >
            Sign In
          </button>
        </form>
      </div>

      {/* Social Login Panel */}
      <div className="w-2/5 flex items-center justify-center border-l px-8 py-4">
        <h3 className="text-sm font-medium text-gray-900">Or sign in with</h3>
        <div className="flex space-x-4 mt-4">
          <button className="bg-white hover:bg-gray-100 p-2 rounded-md border flex items-center justify-center w-full h-10">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="24" height="24" className="fill-current text-blue-600">
              <path d="M498.7 124.8c-4.8-23.2-22.4-41.6-44.8-41.6h-150v-24c0-34.5-27.5-62-62-62s-62 27.5-62 62v24H96.3c-22.4 0-40 18.4-40 41.6v42.4h-.2c-2.6 19.6 7.4 39.8 28.5 51.8V264h137.8l-24.3 24.8v190.4c0 17.5 14.3 31.8 31.8 31.8s31.8-14.3 31.8-31.8V364h139.2v119c0 17.5 14.3 31.8 31.8 31.8s31.8-14.3 31.8-31.8v-190.4l24.3-24.8h137.8V264c11.1-12 21.1-22.2 28.5-31.8z" />
            </svg>
          </button>
          <button className="bg-white hover:bg-gray-100 p-2 rounded-md border flex items-center justify-center w-full h-10">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="24" height="24" className="fill-current text-red-600">
              <path d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256s114.6 256 256 256zm0-480c122.8 0 224 99.38 224 224s-101.2 224-224 224S32 478.8 32 356.8S133.2 132 256 132zm192 320c-17.67 0-32 14.33-32 32s14.33 32 32 32 32-14.33 32-32-14.33-32-32-32zm64 0c-52.97 0-98-42.76-98-96s45.03-96 98-96 96 45.03 96 96-45.03 96-96 96z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginPage1;