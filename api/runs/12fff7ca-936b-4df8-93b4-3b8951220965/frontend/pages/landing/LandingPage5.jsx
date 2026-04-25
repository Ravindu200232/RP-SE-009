import React from "react";

const LandingPage5 = () => {
  return (
    <div className="bg-gray-100 min-h-screen">
      {/* Hero Section */}
      <section className="hero bg-white py-24 px-6 sm:px-12 lg:px-16">
        <div className="container mx-auto text-center">
          <h1 className="text-5xl font-bold mb-8">{SRS.project_name}</h1>
          <p className="text-xl text-gray-700 mb-14">{SRS.tagline}</p>
          <button className={`bg-${SRS.primary_color} text-white py-3 px-6 rounded-lg`}>Get Started</button>
        </div>
      </section>

      {/* Feature Grid Section */}
      <section className="features bg-gray-50 py-12">
        <div className="container mx-auto">
          <h2 className="text-4xl font-bold text-center mb-8">Explore Our Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {SRS.features.map((feature, index) => (
              <div key={index} className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-xl font-semibold mb-2">{feature.name}</h3>
                <p className="text-gray-700 mb-4">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Call to Action Section */}
      <section className="cta bg-white py-16">
        <div className="container mx-auto text-center">
          <h2 className="text-3xl font-bold mb-8">Ready to book your next stay?</h2>
          <p className="text-lg text-gray-700 mb-12">Join millions of users who trust BookStay for their travel needs.</p>
          <button className={`bg-${SRS.primary_color} text-white py-3 px-6 rounded-lg`}>Sign Up Now</button>
        </div>
      </section>

      {/* Footer Section */}
      <footer className="footer bg-gray-200 py-8">
        <div className="container mx-auto flex justify-between items-center">
          <p className="text-sm text-gray-700">© {new Date().getFullYear()} Acme Travel Co. All rights reserved.</p>
          <nav className="flex gap-4">
            {SRS.navigation.map((item, index) => (
              <a key={index} href="#" className="text-gray-600 hover:text-black">{item}</a>
            ))}
          </nav>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage5;