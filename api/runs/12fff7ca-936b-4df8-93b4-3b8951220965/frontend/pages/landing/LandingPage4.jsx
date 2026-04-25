import React from "react";

const LandingPage4 = () => {
  return (
    <div className="bg-gray-100 min-h-screen p-8">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 py-24 flex items-center justify-between shadow-[4px_4px_0_#000] rounded-md border-2 border-black">
        <div>
          <h1 className="text-5xl font-bold text-gray-900">BookStay</h1>
          <p className="mt-3 text-xl font-medium text-gray-700">{SRS.brand.tagline}</p>
        </div>
        <button className="px-6 py-2 bg-blue-400 text-white rounded-md shadow-[4px_4px_0_#000] border-black">Get Started</button>
      </section>

      {/* Feature Grid */}
      <section className="max-w-7xl mx-auto mt-16 grid gap-8 md:grid-cols-2 lg:grid-cols-3">
        {SRS.features.map((feature, index) => (
          <div key={index} className="bg-white p-6 shadow-[4px_4px_0_#000] border-black rounded-md flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">{feature.name}</h2>
              <p className="mt-1 text-sm text-gray-700">{feature.description}</p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
              <path d="M12 2L2 22h20L12 2z"/>
            </svg>
          </div>
        ))}
      </section>

      {/* Call to Action */}
      <section className="max-w-7xl mx-auto mt-16 px-4 flex items-center justify-between shadow-[4px_4px_0_#000] rounded-md border-black">
        <h2 className="text-3xl font-bold text-gray-900">Ready to start planning your next trip?</h2>
        <button className="px-6 py-2 bg-blue-400 text-white rounded-md shadow-[4px_4px_0_#000] border-black">Discover Stays</button>
      </section>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto mt-16 p-8 flex items-center justify-between bg-gray-200">
        <div>
          <h3 className="text-lg font-bold text-gray-900">BookStay</h3>
          <p className="mt-1 text-sm text-gray-700">{SRS.brand.tagline}</p>
        </div>
        <nav className="flex gap-4">
          {SRS.navigation.map((item, index) => (
            <a key={index} href="#" className="text-gray-900 hover:underline">{item}</a>
          ))}
        </nav>
      </footer>
    </div>
  );
};

export default LandingPage4;