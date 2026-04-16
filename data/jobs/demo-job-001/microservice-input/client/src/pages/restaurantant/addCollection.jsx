import axios from "axios";
import { useState } from "react";
import toast from "react-hot-toast";
import { useLocation, useNavigate } from "react-router-dom";
import mediaUpload from "../../utils/mediaUpload";

const backendUrl = import.meta.env.VITE_BACKEND_URL;

export default function AddCollection() {
  const [itemName, setItemName] = useState("");
  const [itemPrice, setItemPrice] = useState("");
  const [itemCategory, setItemCategory] = useState("fastfood");
  const [itemDescription, setItemDescription] = useState("");
  const [itemImages, setItemImages] = useState([]);
  const [itemAvailable, setItemAvailable] = useState(true);

  const navigate = useNavigate();
  const location = useLocation();
  const restaurantId = location.state;

  async function handleAddItem() {
    const token = localStorage.getItem("token");

    if (!token) {
      toast.error("Please login first");
      return;
    }

    try {
      const uploadPromises = Array.from(itemImages).map((img) => mediaUpload(img));
      const imageUrls = await Promise.all(uploadPromises);

      const payload = {
        restaurantId,
        name: itemName,
        price: itemPrice,
        category: itemCategory,
        description: itemDescription,
        available: itemAvailable,
        images: imageUrls,
      };

      const result = await axios.post(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection`,
        payload,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      toast.success(result.data.message || "Item added successfully");
      navigate("/restaurantC/restaurant");
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to add item");
    }
  }

  return (
    <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 px-2 sm:px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-700 mb-6">Add New Item</h1>
      <div className="w-full max-w-md bg-white shadow-xl rounded-lg p-6 flex flex-col space-y-4">
        <input
          type="text"
          placeholder="Item Name"
          value={itemName}
          onChange={(e) => setItemName(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <input
          type="text"
          placeholder="Price"
          value={itemPrice}
          onChange={(e) => setItemPrice(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <select
          value={itemCategory}
          onChange={(e) => setItemCategory(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          <option value="fastfood">Fast Food</option>
          <option value="familyMeals">Family Meals</option>
          <option value="dessert">Dessert</option>
        </select>
        <textarea
          placeholder="Description"
          value={itemDescription}
          onChange={(e) => setItemDescription(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
        />
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">Available:</label>
          <input
            type="checkbox"
            checked={itemAvailable}
            onChange={() => setItemAvailable(!itemAvailable)}
            className="w-5 h-5"
          />
        </div>

        <label className="text-sm text-gray-600">
          Upload Images
          <input
            type="file"
            multiple
            onChange={(e) => setItemImages(e.target.files)}
            className="w-full mt-1 p-2 border border-gray-300 rounded-lg"
          />
        </label>

        {itemImages.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {Array.from(itemImages).map((file, idx) => (
              <img
                key={idx}
                src={URL.createObjectURL(file)}
                alt="preview"
                className="w-full h-24 object-cover rounded"
              />
            ))}
          </div>
        )}

        <div className="flex justify-between space-x-2">
          <button
            onClick={handleAddItem}
            className="w-1/2 bg-blue-500 text-white font-semibold py-2 rounded-lg hover:bg-blue-600 transition"
          >
            Add
          </button>
          <button
            onClick={() => navigate("/admin/item")}
            className="w-1/2 bg-red-500 text-white font-semibold py-2 rounded-lg hover:bg-red-600 transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
