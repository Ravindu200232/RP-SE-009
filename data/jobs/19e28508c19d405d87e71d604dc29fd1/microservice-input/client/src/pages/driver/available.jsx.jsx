import { useEffect, useRef, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";
import mediaUpload from "../../utils/mediaUpload";

export function Available() {
  const fileInputRef = useRef();
  const [driver, setDriver] = useState(null);
  const [formData, setFormData] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    address: "",
    image: "",
    vehicleType: "",
    drNic: "",
    isAvailable: false,
  });

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      const parsed = JSON.parse(storedUser);
      setDriver(parsed);
      setFormData({
        firstName: parsed.firstName,
        lastName: parsed.lastName,
        email: parsed.email,
        phone: parsed.phone,
        address: parsed.address,
        image: parsed.image,
        vehicleType: parsed.vehicleType,
        drNic: parsed.drNic,
        isAvailable: parsed.isAvailable,
      });
    }
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const uploadedUrl = await mediaUpload(file);
      setFormData((prev) => ({
        ...prev,
        image: uploadedUrl,
      }));
      Swal.fire("Uploaded", "Image uploaded successfully", "success");
    } catch (err) {
      console.error(err);
      Swal.fire("Error", "Image upload failed", "error");
    }
  };

  const handleUpdate = async () => {
    try {
      const token = localStorage.getItem("token");
      console.log(driver.id)
      await axios.put(
        `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/driver/${driver.id}`,
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      Swal.fire("Success", "Driver updated successfully", "success");
      localStorage.setItem("user", JSON.stringify({ ...driver, ...formData }));
      setDriver({ ...driver, ...formData });
    } catch (err) {
      console.error(err);
      Swal.fire("Error", "Update failed", "error");
    }
  };

  if (!driver) return <div className="p-6">Loading driver info...</div>;

  return (
    <div className="max-w-4xl mx-auto p-8 bg-gradient-to-r from-purple-600 to-indigo-600 rounded-xl shadow-xl mt-10">
      <div className="flex flex-col items-center mb-6">
        <div
          onClick={() => fileInputRef.current.click()}
          className="cursor-pointer mb-4"
        >
          <img
            src={
              formData.image ||
              "https://via.placeholder.com/150?text=Upload+Image"
            }
            alt="Driver"
            className="w-32 h-32 object-cover rounded-full border-4 border-white shadow-lg hover:opacity-90 transition-all duration-300"
          />
        </div>
        <input
          type="file"
          accept="image/*"
          onChange={handleImageUpload}
          ref={fileInputRef}
          className="hidden"
        />
        <h2 className="text-3xl font-semibold text-white text-center mb-4">
          Driver Availability Profile
        </h2>
      </div>

      <div className="bg-white rounded-lg p-6 shadow-lg">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <input
            type="text"
            name="firstName"
            value={formData.firstName}
            onChange={handleChange}
            placeholder="First Name"
            className="border p-3 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            name="lastName"
            value={formData.lastName}
            onChange={handleChange}
            placeholder="Last Name"
            className="border p-3 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="email"
            name="email"
            value={formData.email}
            disabled
            className="border p-3 rounded-md bg-gray-100 cursor-not-allowed"
          />
          <input
            type="text"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="Phone"
            className="border p-3 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            name="address"
            value={formData.address}
            onChange={handleChange}
            placeholder="Address"
            className="border p-3 rounded-md shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          
          <div className="flex items-center gap-3 mt-3">
            <label htmlFor="isAvailable" className="text-gray-700 font-medium">
              Available for delivery:
            </label>
            <input
              type="checkbox"
              name="isAvailable"
              checked={formData.isAvailable}
              onChange={handleChange}
              className="w-5 h-5"
            />
          </div>
        </div>

        <div className="mt-8 flex justify-center">
          <button
            onClick={handleUpdate}
            className="bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 transition-all duration-200"
          >
            Update Driver Info
          </button>
        </div>
      </div>
    </div>
  );
}
