'use client';
```jsx
import React, { useState } from "react";
import axios from "axios";

function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await axios.post(`${import.meta.env.VITE_AUTH_SERVICE_URL}/api/register`, { email, password });
      window.location.href = "/login";
    } catch (error) {
      console.error(error.response?.data || "Registration failed");
    }
  }

  return (
    <div className="container mx-auto py-16">
      <h2 className="text-3xl font-bold text-gray-900 mb-8">Sign Up</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email Address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="w-full p-4 border rounded-lg mb-4"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="w-full p-4 border rounded-lg mb-4"
        />
        <button type="submit" className="bg-yellow-500 text-gray-900 px-6 py-3 rounded-lg hover:bg-gray-900 hover:text-yellow-500 transition-all uppercase tracking-wide">
          Sign Up
        </button>
      </form>
    </div>
  );
}

export default Register;
```