import React from "react";

const LoginPage4 = () => {
  return (
    <div className="flex h-screen items-center justify-center bg-gray-100">
      <div className="w-full max-w-md p-6 shadow-[4px_4px_0_#000] rounded-md border-2 border-black">
        <header className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">BookStay</h1>
          <p className="mt-1 text-sm text-gray-600">Find your next stay in seconds.</p>
        </header>

        <form className="space-y-6">
          <div className="relative">
            <input
              type="email"
              id="email"
              className="w-full p-3 border-b-2 border-black focus:outline-none"
              placeholder="Email address"
            />
            <label htmlFor="email" className="absolute top-0 left-0 -mt-4 ml-1 text-gray-500">
              Email address
            </label>
          </div>

          <div className="relative">
            <input
              type="password"
              id="password"
              className="w-full p-3 border-b-2 border-black focus:outline-none"
              placeholder="Password"
            />
            <label htmlFor="password" className="absolute top-0 left-0 -mt-4 ml-1 text-gray-500">
              Password
            </label>
          </div>

          <button type="submit" className="w-full p-3 bg-blue-600 text-white font-semibold rounded-md shadow-[4px_4px_0_#000] hover:bg-blue-700 focus:outline-none">
            Sign In
          </button>
        </form>

        <div className="mt-8 flex items-center justify-between">
          <p className="text-sm text-gray-500">Forgot your password?</p>
          <a href="#" className="text-sm font-medium text-blue-600 hover:text-blue-700 focus:outline-none">
            Sign up
          </a>
        </div>

        <footer className="mt-8 border-t border-black pt-4 flex items-center justify-between">
          <p className="text-xs text-gray-500">© 2023 Acme Travel Co.</p>
          <ul className="flex space-x-6">
            {["Discover", "My Trips", "Hosting", "Inbox", "Account"].map((navItem) => (
              <li key={navItem} className="text-xs text-gray-500 hover:text-blue-600 focus:outline-none">
                {navItem}
              </li>
            ))}
          </ul>
        </footer>
      </div>

      <aside className="w-full max-w-sm p-6 shadow-[4px_4px_0_#000] rounded-md border-2 border-black ml-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Sign In with Social</h2>
        <ul className="space-y-3">
          <li className="w-full p-3 bg-blue-600 text-white font-semibold rounded-md shadow-[4px_4px_0_#000] hover:bg-blue-700 focus:outline-none flex items-center justify-center">
            Sign in with Google
          </li>
          <li className="w-full p-3 bg-red-500 text-white font-semibold rounded-md shadow-[4px_4px_0_#000] hover:bg-red-600 focus:outline-none flex items-center justify-center">
            Sign in with Facebook
          </li>
        </ul>
      </aside>
    </div>
  );
};

export default LoginPage4;