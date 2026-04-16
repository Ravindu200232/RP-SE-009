import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import mediaUpload from "../../utils/mediaUpload";
import toast from "react-hot-toast";

const backendUrl = import.meta.env.VITE_BACKEND_URL;

export default function AddRestaurant() {
  const navigate = useNavigate();

  const [restaurantData, setRestaurantData] = useState({
    name: "",
    address: "",
    phone: "",
    description: "",
    images: [],
  });

  const [imageFiles, setImageFiles] = useState([]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setRestaurantData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleImageChange = (e) => {
    setImageFiles([...e.target.files]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const token = localStorage.getItem("token");

      const uploadedUrls = await Promise.all(
        imageFiles.map((file) => mediaUpload(file))
      );

      const response = await axios.post(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/restaurant`,
        {
          ...restaurantData,
          images: uploadedUrls,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      toast.success("Restaurant added successfully!");
      navigate("/restaurantC/restaurant");
    } catch (error) {
      console.error("Error adding restaurant:", error);
      toast.error("Failed to add restaurant. Please try again.");
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Add New Restaurant</h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex flex-col">
          <label htmlFor="name" className="text-lg">
            Restaurant Name
          </label>
          <input
            type="text"
            id="name"
            name="name"
            value={restaurantData.name}
            onChange={handleChange}
            className="border p-2 rounded-lg"
            required
          />
        </div>

        <div className="flex flex-col">
          <label htmlFor="address" className="text-lg">
            Address
          </label>
          <input
            type="text"
            id="address"
            name="address"
            value={restaurantData.address}
            onChange={handleChange}
            className="border p-2 rounded-lg"
            required
          />
        </div>

        <div className="flex flex-col">
          <label htmlFor="phone" className="text-lg">
            Phone Number
          </label>
          <input
            type="text"
            id="phone"
            name="phone"
            value={restaurantData.phone}
            onChange={handleChange}
            className="border p-2 rounded-lg"
            required
          />
        </div>

        <div className="flex flex-col">
          <label htmlFor="description" className="text-lg">
            Description
          </label>
          <textarea
            id="description"
            name="description"
            value={restaurantData.description}
            onChange={handleChange}
            className="border p-2 rounded-lg"
            rows="4"
            required
          ></textarea>
        </div>

        <div className="flex flex-col">
          <label htmlFor="images" className="text-lg">
            Restaurant Images
          </label>
          <input
            type="file"
            id="images"
            multiple
            onChange={handleImageChange}
            className="border p-2 rounded-lg"
            required
          />
        </div>

        <div className="mt-6">
          <button
            type="submit"
            className="bg-green-600 text-white py-2 px-6 rounded-lg"
          >
            Add Restaurant
          </button>
        </div>
      </form>
    </div>
  );
}
