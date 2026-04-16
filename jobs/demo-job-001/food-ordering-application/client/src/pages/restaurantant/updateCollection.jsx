import axios from "axios";
import { useState } from "react";
import toast from "react-hot-toast";
import { useLocation, useNavigate } from "react-router-dom";
import mediaUpload from "../../utils/mediaUpload";



export default function UpdateCollection() {
  const navigate = useNavigate();
  const location = useLocation();
  const data = location.state;

  const [itemId] = useState(data.itemId);
  const [itemName, setItemName] = useState(data.name);
  const [itemPrice, setItemPrice] = useState(data.price);
  const [itemCategory, setItemCategory] = useState(data.category);
  const [itemDescription, setItemDescription] = useState(data.description);
  const [itemAvailable, setItemAvailable] = useState(data.available);
  const [itemImages, setItemImages] = useState([]);
  const [existingImages, setExistingImages] = useState(data.images || []);

  async function handleUpdateItem() {
    const token = localStorage.getItem("token");

    if (!token) {
      toast.error("Please login first");
      return;
    }

    let updatedImages = existingImages;

    if (itemImages.length > 0) {
      try {
        const uploadPromises = Array.from(itemImages).map((img) => mediaUpload(img));
        const uploaded = await Promise.all(uploadPromises);
        updatedImages = uploaded;
      } catch (err) {
        toast.error("Image upload failed");
        return;
      }
    }

    try {
      const result = await axios.put(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/update/${data._id}`,
        {
          name: itemName,
          price: itemPrice,
          category: itemCategory,
          description: itemDescription,
          available: itemAvailable,
          images: updatedImages,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      toast.success(result.data.message || "Item updated successfully");
      navigate("/restaurantC/restaurant");
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to update item");
    }
  }

  return (
    <div className="w-full min-h-screen flex flex-col items-center justify-center bg-gray-100 p-4">
      <h1 className="text-2xl font-bold text-gray-700 mb-6">Update Item</h1>
      <div className="w-[400px] bg-white shadow-xl rounded-lg p-6 flex flex-col space-y-4">
        <input
          type="text"
          disabled
          value={itemId}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100"
        />
        <input
          type="text"
          placeholder="Item Name"
          className="w-full px-4 py-2 border border-gray-300 rounded-lg"
          value={itemName}
          onChange={(e) => setItemName(e.target.value)}
        />
        <input
          type="number"
          placeholder="Item Price"
          className="w-full px-4 py-2 border border-gray-300 rounded-lg"
          value={itemPrice}
          onChange={(e) => setItemPrice(e.target.value)}
        />
        <select
          value={itemCategory}
          onChange={(e) => setItemCategory(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg"
        >
         <option value="fastfood">Fast Food</option>
          <option value="familyMeals">Family Meals</option>
          <option value="dessert">Dessert</option>
        </select>
        <textarea
          placeholder="Description"
          className="w-full px-4 py-2 border border-gray-300 rounded-lg resize-none"
          value={itemDescription}
          onChange={(e) => setItemDescription(e.target.value)}
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
          Upload New Images (optional)
          <input
            type="file"
            multiple
            onChange={(e) => setItemImages(e.target.files)}
            className="w-full mt-1 p-2 border border-gray-300 rounded-lg"
          />
        </label>

        {existingImages.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {existingImages.map((imgUrl, idx) => (
              <img
                key={idx}
                src={imgUrl}
                alt="existing"
                className="w-full h-24 object-cover rounded"
              />
            ))}
          </div>
        )}

        <div className="flex justify-between space-x-2">
          <button
            onClick={handleUpdateItem}
            className="w-1/2 bg-blue-500 text-white font-semibold py-2 rounded-lg hover:bg-blue-600 transition"
          >
            Update
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
