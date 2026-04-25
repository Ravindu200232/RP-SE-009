import React from "react";

const LandingPage1 = () => {
  return (
    <div className="bg-white">
      {/* Hero Section */}
      <section className="py-24 flex items-center justify-center">
        <div className="max-w-screen-xl mx-auto px-6 text-center">
          <h1 className="text-5xl font-bold mb-4">{SRS.brand.name}</h1>
          <p className="text-gray-700 text-lg mb-8">{SRS.tagline}</p>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-24">
        <div className="max-w-screen-xl mx-auto px-6 grid gap-8 md:grid-cols-3">
          {SRS.features.map((feature, index) => (
            <div
              key={index}
              className="border border-gray-200 p-6 rounded-lg hover:bg-gray-50 transition duration-150 ease-in-out"
            >
              <h2 className="text-xl font-semibold mb-2">{feature.name}</h2>
              <p className="text-gray-700 text-sm">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Call to Action */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-screen-xl mx-auto px-6 flex items-center justify-between">
          <button className="bg-blue-700 text-white py-4 px-8 rounded hover:bg-blue-800 transition duration-150 ease-in-out">
            Get Started
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 bg-gray-50 border-t border-gray-200 text-center">
        <p className="text-sm text-gray-700">© {new Date().getFullYear()} Acme Travel Co.</p>
      </footer>
    </div>
  );
};

export default LandingPage1;