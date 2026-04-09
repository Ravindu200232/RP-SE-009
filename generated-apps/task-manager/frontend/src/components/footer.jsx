```jsx
import React from "react";

function Footer() {
  return (
    <footer className="bg-gray-800 text-white p-6">
      <div className="container mx-auto flex justify-between items-center">
        <p>&copy; {new Date().getFullYear()} Task Manager</p>
        <nav>
          <ul className="flex space-x-4">
            <li><a href="#" className="hover:text-yellow-500">About Us</a></li>
            <li><a href="#" className="hover:text-yellow-500">Contact Us</a></li>
            <li><a href="#" className="hover:text-yellow-500">Privacy Policy</a></li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}

export default Footer;
```