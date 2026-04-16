import axios from "axios";
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useNavigation } from "react-router-dom";
import Swal from "sweetalert2";

export default function RestaurantCreate() {
  const [restaurants, setRestaurants] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const OwnerName = localStorage.getItem("user")


  const handleUpdateRestaurant = async (id) => {

    navigate("/restaurantC/restaurant/edit", { state: id });
  }

  const handleItem = async (id) => {
    navigate("/restaurantC/restaurant/collection", { state: id });
  }


  const handleDeleteRestaurant = async (id) => {
    const result = await Swal.fire({
      title: "Are you sure?",
      text: "You won't be able to revert this!",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#d33",
      cancelButtonColor: "#3085d6",
      confirmButtonText: "Yes, delete it!",
      cancelButtonText: "No, cancel",
    });

    if (result.isConfirmed) {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.delete(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/delete/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        Swal.fire({
          icon: "success",
          title: "Deleted!",
          text: response.data.message,
          timer: 1500,
          showConfirmButton: false,
        });
        fetchRestaurants();
        setRestaurants((prevRestaurants) =>
          prevRestaurants.filter((restaurant) => restaurant._id !== id)
        );
      } catch (error) {
        console.error("Error status:", error);
        Swal.fire({
          icon: "error",
          title: "Oops...",
          text: "Failed to delete the restaurant.",
        });
      }
    }
  };

  const fetchRestaurants = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRestaurants(response.data);
    } catch (error) {
      console.error("Failed to fetch restaurants:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRestaurants();
  }, []);

  const handleToggleShop = async (id, shouldOpen) => {
    try {
      const token = localStorage.getItem("token");
      const endpoint = shouldOpen
        ? `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/isOpen/${id}`
        : `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/isClose/${id}`;

      const response = await axios.post(
        endpoint,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      Swal.fire({
        icon: "success",
        title: "Success",
        text: response.data.message,
        timer: 1500,
        showConfirmButton: false,
      });

      fetchRestaurants(); // Refresh list
    } catch (error) {
      console.error("Error toggling shop status:", error);
      Swal.fire({
        icon: "error",
        title: "Oops...",
        text: "Failed to update shop status.",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="w-16 h-16 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto mt-8 px-4">
      <h1 className="text-3xl font-bold text-center mb-8">Restaurants</h1>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {restaurants.map((restaurant) => (
          //
          
          <div
            key={restaurant._id}
            className="bg-white shadow-md rounded-xl p-4 space-y-3"
          >
            <button onClick={() => handleItem(restaurant._id)}>
            <img
              src={restaurant.images?.[0] || "/default-restaurant.jpg"}
              alt={restaurant.name}
              className="w-full cur h-48 object-cover rounded-md"
            />
            </button>
            <h2 className="text-xl font-semibold">{restaurant.name}</h2>
            <p><strong>Owner Name:</strong> {restaurant.ownerName}</p>
            <p><strong>Address:</strong> {restaurant.address}</p>
            <p><strong>Phone:</strong> {restaurant.phone}</p>
            <p><strong>Description:</strong> {restaurant.description}</p>
            <p>
              <strong>Status:</strong>{" "}
              <span className={`font-semibold ${restaurant.isOpen ? "text-green-600" : "text-red-500"}`}>
                {restaurant.isOpen ? "Open" : "Closed"}
              </span>
            </p>
            <p>
              <strong>Verified:</strong>{" "}
              <span className={`font-semibold ${restaurant.verified ? "text-green-600" : "text-red-500"}`}>
                {restaurant.verified ? "Yes" : "No"}
              </span>
            </p>
            {restaurant.isOpen ? (
              <button
                onClick={() => handleToggleShop(restaurant._id, false)}
                className="w-full mt-2 bg-red-600 hover:bg-red-700 text-white py-2 rounded-lg"
              >
                Close Shop
              </button>
            ) : (
              <button
                onClick={() => handleToggleShop(restaurant._id, true)}
                className="w-full mt-2 bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg"
              >
                Open Shop
              </button>

             
              
            )}

              <div className="flex flex-row gap-2">
                <button
                  onClick={() => handleDeleteRestaurant(restaurant._id)}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white py-2 rounded-lg"
                >
                  Delete
                </button>

                <button
                  onClick={() => handleUpdateRestaurant(restaurant._id)}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg"
                >
                  Update
                </button>
              </div>

          </div>
         
          //
        ))}
      </div>

      <Link
        to="/restaurantC/restaurant/add"
        className="fixed bottom-10 right-10 p-5 rounded-full text-white bg-red-600 hover:bg-red-700 animate-bounce shadow-lg"
      >
        Add Restaurant
      </Link>
    </div>
  );
}

