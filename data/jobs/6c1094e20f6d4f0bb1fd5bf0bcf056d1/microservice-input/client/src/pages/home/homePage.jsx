import { Route, Routes } from "react-router-dom";
import Header from "../../components/header";
import Contact from "./contacts";
import Item from "./item";
import Home from "./home";
import ErrorNotFound from "./error";
import ProductOverview from "./productOverview";
import { BookingPage } from "./bookingpage";
import { Profile } from "./profile";
import RestaurantDetails from "./restaurantDetails";
import Restaurant from "./restaurant";
import { Location } from "./location";

export default function HomePage() {
  return (
    <>
      {/* Header is already fixed/positioned inside the Header component */}
      <Header />

      {/* Page content — no top margin needed; Home hero is full-screen,
          other pages use their own top padding via their own styles */}
      <main style={{ minHeight: "100vh" }}>
        <Routes>
          <Route path="/contact"        element={<Contact />} />
          <Route path="/restaurant"     element={<Restaurant />} />
          <Route path="/restaurant/*"   element={<RestaurantDetails />} />
          <Route path="/item"           element={<Item />} />
          <Route path="/product/:key"   element={<ProductOverview />} />
          <Route path="/cart"           element={<BookingPage />} />
          <Route path="/location"       element={<Location />} />
          <Route path="/profile"        element={<Profile />} />
          <Route path="/"              element={<Home />} />
          <Route path="/*"             element={<ErrorNotFound />} />
        </Routes>
      </main>
    </>
  );
}