'use client';
```jsx
import React, { useState } from "react";

function Header() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <header className="fixed w-full z-50 top-0 left-0 bg-transparent">
        <nav className="container mx-auto flex justify-between items-center py-4 px-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Task Manager</h2>
          </div>
          <button onClick={() => setIsOpen(!isOpen)} className="block md:hidden focus:outline-none">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5m-16.5 3h15m-16.5 3h15m-16.5 3h15"></path>
            </svg>
          </button>
        </nav>

        {isOpen && (
          <div className="fixed inset-0 bg-black opacity-25 z-40" onClick={() => setIsOpen(false)}></div>
        )}

        <aside className={`md:block fixed top-0 left-0 h-full w-64 bg-white shadow-md transform transition-transform ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <ul className="mt-10">
            <li><a href="#" className="block px-4 py-3 text-gray-700 hover:bg-blue-500 hover:text-white">Home</a></li>
            <li><a href="/login" className="block px-4 py-3 text-gray-700 hover:bg-blue-500 hover:text-white">Login</a></li>
            <li><a href="/register" className="block px-4 py-3 text-gray-700 hover:bg-blue-500 hover:text-white">Register</a></li>
          </ul>
        </aside>
      </header>
    </>
  );
}

export default Header;
```