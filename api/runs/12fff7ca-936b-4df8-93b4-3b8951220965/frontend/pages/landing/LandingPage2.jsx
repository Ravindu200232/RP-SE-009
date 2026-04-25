import React from "react";

const LandingPage2 = () => {
  return (
    <div className="bg-white min-h-screen flex flex-col">
      {/* Hero Section */}
      <section className="hero bg-blue-500 text-white p-16 rounded-2xl shadow-lg mb-8">
        <h1 className="text-4xl font-bold">BookStay</h1>
        <p className="mt-4">{`Find your next stay in seconds.`}</p>
      </section>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 p-8">
        {features.map((feature) => (
          <article key={feature.name} className="bg-white rounded-2xl shadow-lg p-6 flex items-center justify-between">
            <div>
              <h4 className="text-xl font-bold">{feature.name}</h4>
              <p>{feature.description}</p>
            </div>
            <span className="material-icons text-blue-500">arrow_forward</span>
          </article>
        ))}
      </div>

      {/* Call to Action */}
      <section className="cta bg-blue-500 text-white p-16 rounded-2xl shadow-lg mb-8 flex justify-center">
        <button className="bg-white text-blue-500 px-8 py-4 rounded-full font-bold">Get Started</button>
      </section>

      {/* Footer */}
      <footer className="bg-gray-100 p-8 flex justify-between items-center">
        <nav className="flex gap-6">
          {navigation.map((item) => (
            <a key={item} href="#" className="text-blue-500 font-bold hover:text-black">
              {item}
            </a>
          ))}
        </nav>
        <p className="text-gray-700">© 2023 Acme Travel Co.</p>
      </footer>
    </div>
  );
};

const features = [
  {
    name: "Search Rooms",
    description: "Filter rooms by city, dates, and guest count."
  },
  {
    name: "Room Details",
    description: "View images, amenities, reviews, and host info."
  },
  {
    name: "Secure Checkout",
    description: "Stripe payments with itemised pricing and tax."
  },
  {
    name: "Host Dashboard",
    description: "Manage listings, calendars, and bookings."
  },
  {
    name: "Reviews",
    description: "Post-stay rating and written feedback."
  }
];

const navigation = [
  "Discover",
  "My Trips",
  "Hosting",
  "Inbox",
  "Account"
];

export default LandingPage2;