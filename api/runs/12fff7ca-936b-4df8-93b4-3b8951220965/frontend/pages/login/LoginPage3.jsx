import React from "react";

const LoginPage3 = () => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 to-gray-800">
      <div className="bg-white/30 backdrop-blur-lg rounded-xl shadow-md p-12 max-w-sm w-full mx-auto flex flex-col items-center space-y-4">
        <h1 className="text-2xl font-bold text-blue-600">BookStay</h1>
        <p className="text-gray-700">Sign In to your account</p>

        <form action="#" className="space-y-3 w-full">
          <div className="relative">
            <input
              type="email"
              placeholder="Email address"
              className="w-full py-2 px-4 rounded-md border border-gray-300 bg-white/50 focus:outline-none focus:border-blue-600"
            />
            <span className="absolute inset-y-0 right-0 flex items-center pr-3">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-6 h-6 text-gray-700"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0c0 1.105-.895 2-2 2a1.994 1.994 0 01-1.414-.586l-.828-.828A2 2 0 0112.586 11h.818c.9 0 1.73-.5 1.73-1.1 0-.6-.43-1.1-.95-1.2l-.828-.828A1.994 1.994 0 0116 12zm-4-4a1 1 0 10-1 1 1 1 0 001-1z"
                />
              </svg>
            </span>
          </div>

          <div className="relative">
            <input
              type="password"
              placeholder="Password"
              className="w-full py-2 px-4 rounded-md border border-gray-300 bg-white/50 focus:outline-none focus:border-blue-600"
            />
            <span className="absolute inset-y-0 right-0 flex items-center pr-3">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-6 h-6 text-gray-700"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 15v2m-6 4h12a2 2 0 002-2V5a2 2 0 00-2-2H6a2 2 0 00-2 2v14a2 2 0 002 2z"
                />
              </svg>
            </span>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none"
          >
            Sign In
          </button>

          <p className="text-center text-sm">
            Don't have an account?{" "}
            <a href="#" className="underline text-blue-600">
              Register here
            </a>
          </p>
        </form>

        <div className="flex items-center space-x-2 mt-4">
          <hr className="w-full border-gray-300" />
          <span className="text-sm text-gray-500">or</span>
          <hr className="w-full border-gray-300" />
        </div>

        <button
          type="button"
          className="flex items-center justify-center w-full py-2 px-4 bg-white/50 rounded-md hover:bg-white/70 focus:outline-none space-x-2 text-blue-600"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path d="M19.78 6h-.14a2.002 2.002 0 00-1.99-1.86l-.18-.12A3 3 0 0013.58 2H10.42a3 3 0 00-2.91 1.14L7.22 4.14A2 2 0 006 6h-.14a1 1 0 01-.99-1V2a1 1 0 011-1H5v22h14V5a1 1 0 01.99 1z" />
          </svg>
          <span>Sign in with Google</span>
        </button>

        <div className="mt-6">
          <p className="text-center text-gray-700">BookStay | Find your next stay in seconds.</p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage3;