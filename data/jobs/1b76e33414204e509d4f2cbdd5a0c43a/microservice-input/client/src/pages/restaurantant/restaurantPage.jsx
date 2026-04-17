import { CgProfile } from "react-icons/cg"; 
import { MdOutlinePayments, MdRateReview } from "react-icons/md";
import { BsGraphDown } from "react-icons/bs";
import { CiSpeaker, CiBookmarkCheck, CiUser } from "react-icons/ci";
import { Link, Route, Routes } from "react-router-dom";
import { useState } from "react";
import { HiOutlineMenuAlt3, HiOutlineX } from "react-icons/hi";





import { RestaurantReview } from "./restaurantReview";

import RestaurantCreate from "./restaurantCreate";

import AddRestaurant from "./addResturant";
import UpdateRestaurant from "./updateRestaurant";
import CollectionPage from "./collectionPage";
import AddCollection from "./addCollection";
import UpdateCollection from "./updateCollection";
import RestaurantOrder from "./restaurantOrder";
import { Profile } from "./profile";

export default function RestaurantPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toggleSidebar = () => setSidebarOpen(!sidebarOpen);
  const closeSidebar = () => setSidebarOpen(false);

  const [token, setToken] = useState(localStorage.getItem("token"));
  if (!token) {
    window.location.href = "/login";
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile Menu Toggle */}
      <div className="md:hidden fixed top-4 left-4 z-50">
        <button onClick={toggleSidebar} className="text-3xl text-gray-800">
          {sidebarOpen ? <HiOutlineX /> : <HiOutlineMenuAlt3 />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={`fixed md:static z-40 top-0 left-0 h-full w-64 bg-white shadow-md transform transition-transform duration-300 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        } flex flex-col justify-between`}
      >
        <div>
          <div className="flex items-center justify-center h-20 border-b">
            <h1 className="text-2xl font-bold text-gray-800">Restaurant Owner Panel</h1>
          </div>

          <nav className="mt-6">
            {[
              {
                to: "/restaurantC/booking",
                icon: <CiBookmarkCheck />,
                label: "Restaurant Order",
              },
             
              {
                to: "/restaurantC/restaurant",
                icon: <CiBookmarkCheck />,
                label: "Restaurant",
              },
              {
                to: "/restaurantC/profile",
                icon: <CgProfile />,
                label: "Profile",
              },
         
              { to: "/restaurantC/review", icon: <MdRateReview />, label: "Reviews" },
              ,
              
            ].map(({ to, icon, label }) => (
              <Link
                key={to}
                to={to}
                onClick={closeSidebar}
                className="flex items-center px-6 py-3 text-gray-700 hover:bg-gray-200"
              >
                {icon}
                <span className="ml-4">{label}</span>
              </Link>
            ))}
          </nav>
        </div>

        {/* Logout Button */}
        <button
          onClick={() => {
            localStorage.clear();
            window.location.href = "/login";
          }}
          className="w-full text-left flex items-center px-6 py-3 text-red-600 hover:bg-red-100 border-t"
        >
          <span className="ml-4 font-semibold">Logout</span>
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-4 :ml-64 bg-gray-100 overflow-y-auto">
        <Routes>
          <Route path="/booking" element={<RestaurantOrder />} />
          <Route path="/restaurant/collection" element={<CollectionPage />} />
          <Route path="/restaurant/collection/add" element={<AddCollection />} />
          <Route path="/restaurant/collection/update" element={<UpdateCollection />} />
          <Route path="/profile" element={<Profile />} />

          <Route path="/review" element={<RestaurantReview />} />

          <Route path="/restaurant/" element={<RestaurantCreate />} />
          <Route path="/restaurant/add" element={<AddRestaurant />} />
          <Route path="/restaurant/edit" element={<UpdateRestaurant />} />

        </Routes>
      </main>
    </div>
  );
}
