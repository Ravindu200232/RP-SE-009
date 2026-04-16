import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate, useLocation } from "react-router-dom";
import toast from "react-hot-toast";

export default function UpdateRestaurant() {
  const location = useLocation();
  const navigate = useNavigate();
  console.log(location.state)
  const id = location.state;

  const [restaurantData, setRestaurantData] = useState({
    name: "",
    address: "",
    phone: "",
    description: "",
    images: [""], // array of image URLs
  });

  const backendUrl = import.meta.env.VITE_BACKEND_URL;

  useEffect(() => {
    const fetchRestaurant = async () => {
      if (!id) {
        console.error("Restaurant ID is missing");
        return;
      }
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/getOne/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        console.log(response)
        const { name, address, phone, description, images } = response.data;
        setRestaurantData({
          name,
          address,
          phone,
          description,
          images: images.length ? images : [""],
        });
      } catch (error) {
        console.error("Error fetching restaurant details:", error);
        toast.error("Failed to fetch restaurant");
      }
    };

    fetchRestaurant();
  }, [id]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setRestaurantData((prev) => ({ ...prev, [name]: value }));
  };

  const handleImageChange = (index, value) => {
    const newImages = [...restaurantData.images];
    newImages[index] = value;
    setRestaurantData((prev) => ({ ...prev, images: newImages }));
  };

  const addImageField = () => {
    setRestaurantData((prev) => ({
      ...prev,
      images: [...prev.images, ""],
    }));
  };

  const removeImageField = (index) => {
    const newImages = restaurantData.images.filter((_, i) => i !== index);
    setRestaurantData((prev) => ({
      ...prev,
      images: newImages.length ? newImages : [""],
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem("token");
      const response = await axios.put(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant/update/${id}`,
        restaurantData,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      toast.success("Restaurant updated!");
      navigate("/restaurantC/restaurants");
    } catch (error) {
      console.error("Error updating restaurant:", error);
      toast.error("Update failed");
    }
  };

  return (
    <div className="max-w-3xl mx-auto mt-10 px-4">
      <h2 className="text-2xl font-bold mb-6 text-center">Update Restaurant</h2>
      <form onSubmit={handleSubmit} className="space-y-5 bg-white p-6 rounded-xl shadow-md">
        <div>
          <label className="block mb-1 font-medium">Restaurant Name</label>
          <input
            type="text"
            name="name"
            value={restaurantData.name}
            onChange={handleChange}
            className="w-full border p-2 rounded-lg"
            required
          />
        </div>

        <div>
          <label className="block mb-1 font-medium">Address</label>
          <input
            type="text"
            name="address"
            value={restaurantData.address}
            onChange={handleChange}
            className="w-full border p-2 rounded-lg"
            required
          />
        </div>

        <div>
          <label className="block mb-1 font-medium">Phone</label>
          <input
            type="text"
            name="phone"
            value={restaurantData.phone}
            onChange={handleChange}
            className="w-full border p-2 rounded-lg"
            required
          />
        </div>

        <div>
          <label className="block mb-1 font-medium">Description</label>
          <textarea
            name="description"
            rows="4"
            value={restaurantData.description}
            onChange={handleChange}
            className="w-full border p-2 rounded-lg"
            required
          />
        </div>

        <div>
          <label className="block mb-2 font-medium">Image URLs</label>
          {restaurantData.images.map((img, index) => (
            <div key={index} className="flex gap-2 mb-2 items-center">
              <input
                type="text"
                value={img}
                onChange={(e) => handleImageChange(index, e.target.value)}
                className="flex-1 border p-2 rounded-lg"
              />
              <button
                type="button"
                onClick={() => removeImageField(index)}
                className="text-red-600 hover:underline"
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addImageField}
            className="text-blue-500 hover:underline"
          >
            + Add Image
          </button>
        </div>

        <button
          type="submit"
          className="bg-blue-600 text-white px-6 py-2 rounded-lg w-full"
        >
          Update Restaurant
        </button>
      </form>
    </div>
  );
}
