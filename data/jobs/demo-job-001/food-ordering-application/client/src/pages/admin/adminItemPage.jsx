import { useEffect, useState } from "react";
import { FiEdit, FiTrash2 } from "react-icons/fi";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "react-hot-toast";

export default function AdminItemPage() {
  const [items, setItems] = useState([]);
  const [itemsLoaded, setItemsLoaded] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const restaurantId = location.state;

  useEffect(() => {
    if (!itemsLoaded && restaurantId) {
      const token = localStorage.getItem("token");
      axios
        .get(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/getAll/${restaurantId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        .then((res) => {
          setItems(res.data);
          setItemsLoaded(true);
        })
        .catch((err) => {
          console.error(err);
        });
    }
  }, [itemsLoaded, restaurantId]);

  const handleDelete = (itemId) => {
    const token = localStorage.getItem("token");

    toast(
      (t) => (
        <span>
          Are you sure you want to delete?
          <div className="mt-2 flex justify-end space-x-2">
            <button
              onClick={() => {
                toast.dismiss(t.id);
                axios
                  .delete(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/delete/${itemId}`, {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                  .then(() => {
                    setItems((prev) => prev.filter((item) => item._id !== itemId));
                    setItemsLoaded(false);
                    toast.success("Item deleted successfully!");
                  })
                  .catch((err) => {
                    console.error(err);
                    toast.error("Failed to delete the item.");
                  });
              }}
              className="bg-red-500 text-white px-3 py-1 rounded text-sm"
            >
              Yes
            </button>
            <button
              onClick={() => toast.dismiss(t.id)}
              className="bg-gray-300 px-3 py-1 rounded text-sm"
            >
              No
            </button>
          </div>
        </span>
      ),
      {
        duration: 10000,
      }
    );
  };

  const handleApprove = (collectionId) => {
    const token = localStorage.getItem("token");
    axios
      .post(`${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/collection/isApprove/${collectionId}`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then(() => {
        toast.success("Item approved successfully!");
        setItemsLoaded(false);
      })
      .catch((err) => {
        console.error(err);
        toast.error("Failed to approve the item.");
      });
  };

  return (
    <div className="w-full h-full p-4 sm:p-6 flex flex-col items-center">
      <h1 className="text-2xl sm:text-3xl font-bold text-gray-700 mb-6">
        Collection Management
      </h1>

      {!itemsLoaded ? (
        <div className="flex justify-center items-center h-64">
          <div className="w-12 h-12 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="w-full max-w-6xl">
          {/* Mobile Layout */}
          <div className="sm:hidden space-y-4">
            {items.map((product) => (
              <div
                key={product.itemId}
                className="border rounded-lg shadow p-4 bg-white space-y-2"
              >
                <div className="text-sm font-semibold text-gray-800">
                  {product.name} - Rs.{product.price}
                </div>
                <img
                  src={product.images?.[0]}
                  alt={product.name}
                  className="h-32 w-full object-cover rounded-lg"
                />
                <div className="text-sm text-gray-500">
                  Category: {product.category}
                </div>
                <div className="text-sm text-gray-500">{product.description}</div>
                <div
                  className={`text-sm font-semibold ${
                    product.available ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {product.available ? "In Stock" : "Out of Stock"}
                </div>
                {!product.approve && (
                  <button
                    onClick={() => handleApprove(product._id)}
                    className="w-full bg-green-600 text-white py-1 rounded text-sm mb-2"
                  >
                    Approve
                  </button>
                )}
                <div className="flex justify-end space-x-4 pt-2">
                  <button
                    onClick={() => navigate("/admin/item/edit", { state: product })}
                    className="text-blue-500 hover:text-blue-700"
                  >
                    <FiEdit size={18} />
                  </button>
                  <button
                    onClick={() => handleDelete(product._id)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <FiTrash2 size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop Layout */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full border border-gray-200 shadow-lg rounded-lg overflow-hidden">
              <thead>
                <tr className="bg-gray-800 text-white">
                  <th className="py-3 px-4">Item ID</th>
                  <th className="py-3 px-4">Image</th>
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Price</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Description</th>
                  <th className="py-3 px-4">Available</th>
                  <th className="py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((product) => (
                  <tr
                    key={product.itemId}
                    className="border-b hover:bg-gray-100 transition"
                  >
                    <td className="py-3 px-4 text-center">{product.itemId}</td>
                    <td className="py-3 px-4 text-center">
                      <img
                        src={product.images?.[0]}
                        alt={product.name}
                        className="h-16 w-16 object-cover rounded"
                      />
                    </td>
                    <td className="py-3 px-4 text-center">{product.name}</td>
                    <td className="py-3 px-4 text-center">Rs.{product.price}</td>
                    <td className="py-3 px-4 text-center">{product.category}</td>
                    <td className="py-3 px-4 text-center">{product.description}</td>
                    <td
                      className={`py-3 px-4 text-center font-semibold ${
                        product.available ? "text-green-600" : "text-red-600"
                      }`}
                    >
                      {product.available ? "In Stock" : "Out of Stock"}
                    </td>
                    <td className="py-3 px-4 text-center flex justify-center space-x-3">
                      {!product.approve && (
                        <button
                          onClick={() => handleApprove(product._id)}
                          className="text-green-600 hover:text-green-800"
                          title="Approve"
                        >
                          ✔️
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(product._id)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <FiTrash2 size={20} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}