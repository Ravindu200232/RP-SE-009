import React from "react";

const LandingPage3 = () => {
  return (
    <div className="bg-gradient-to-br from-white/10 via-blue-100 to-white/20 min-h-screen flex items-center justify-center p-8">
      {/* Hero Section */}
      <section className="max-w-6xl mx-auto bg-white/30 backdrop-blur-lg rounded-xl shadow-md p-10 space-y-4 text-gray-900">
        <h1 className="text-5xl font-bold">Welcome to BookStay</h1>
        <p className="text-xl">{`Find your next stay in seconds.`}</p>
        <div className="flex items-center gap-2">
          <button className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">Get Started</button>
          <a href="#" className="text-blue-600 underline hover:text-blue-700 transition-colors">Learn More</a>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="max-w-6xl mx-auto mt-12 grid gap-8 md:grid-cols-3">
        {features.map((feature, index) => (
          <article key={index} className="bg-white/30 backdrop-blur-lg rounded-xl shadow-md p-4 flex items-center justify-between">
            <div>
              <h3 className="text-xl font-semibold">{feature.name}</h3>
              <p>{feature.description}</p>
            </div>
            <span className="material-icons text-blue-600">arrow_forward</span>
          </article>
        ))}
      </section>

      {/* CTA Section */}
      <section className="max-w-6xl mx-auto mt-12 bg-white/30 backdrop-blur-lg rounded-xl shadow-md p-8 flex items-center justify-between">
        <h2 className="text-4xl font-bold">Ready to book your next stay?</h2>
        <button className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">Book Now</button>
      </section>

      {/* Footer */}
      <footer className="max-w-6xl mx-auto mt-12 flex justify-between items-center bg-white/30 backdrop-blur-lg rounded-tl-xl rounded-tr-xl shadow-md p-4">
        <div>© 2023 Acme Travel Co.</div>
        <nav className="flex gap-4">
          {navigation.map((item, index) => (
            <a key={index} href="#" className="text-gray-900 hover:text-blue-600 transition-colors">{item}</a>
          ))}
        </nav>
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

export default LandingPage3;