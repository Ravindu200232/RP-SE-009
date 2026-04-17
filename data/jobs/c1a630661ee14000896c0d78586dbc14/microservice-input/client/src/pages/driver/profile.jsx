import { useEffect, useRef, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";
import mediaUpload from "../../utils/mediaUpload";

import L from "leaflet";
import "leaflet/dist/leaflet.css";

export function Profile() {
  const [user, setUser] = useState(null);
  const fileInputRef = useRef();
  const [formData, setFormData] = useState({
    email: "",
    firstName: "",
    lastName: "",
    address: "",
    phone: "",
    image: "",
  });
  const [passwords, setPasswords] = useState({ oldPassword: "", newPassword: "" });

  const [deliveries, setDeliveries] = useState([]);
  const [deliveriesLoading, setDeliveriesLoading] = useState(true);
  const [expandedDeliveryId, setExpandedDeliveryId] = useState(null);
  const mapRefs = useRef({});

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      const parsed = JSON.parse(storedUser);
      setUser(parsed);
      setFormData({
        email: parsed.email,
        firstName: parsed.firstName,
        lastName: parsed.lastName,
        address: parsed.address,
        phone: parsed.phone,
        image: parsed.image,
      });
    }
  }, []);

  useEffect(() => {
    const fetchDeliveries = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(`${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/driver`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const userDeliveries = response.data.filter(d => d.customerEmail === user?.email);
        setDeliveries(userDeliveries);
      } catch (err) {
        Swal.fire("Error", "Could not fetch delivery history.", "error");
      } finally {
        setDeliveriesLoading(false);
      }
    };
    if (user) fetchDeliveries();
  }, [user]);

  const handleDriverLocation = async (deliveryId) => {
    try {
      const res = await axios.get(`${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery/loc/${deliveryId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      const delivery = res.data;

      setDeliveries(prev =>
        prev.map(d => (d._id === deliveryId ? { ...d, lat: delivery.lat, lng: delivery.lng } : d))
      );
      setExpandedDeliveryId(deliveryId);
    } catch (err) {
      Swal.fire("Error", "Could not fetch driver location.", "error");
    }
  };

  useEffect(() => {
    if (expandedDeliveryId && mapRefs.current[expandedDeliveryId]) {
      const delivery = deliveries.find(d => d._id === expandedDeliveryId);
      if (!delivery?.lat || !delivery?.lng) return;

      const mapContainer = mapRefs.current[expandedDeliveryId];
      mapContainer.innerHTML = ""; // Reset map

      const map = L.map(mapContainer).setView([delivery.lat, delivery.lng], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);
      L.marker([delivery.lat, delivery.lng]).addTo(map).bindPopup("Driver's Location").openPopup();
    }
  }, [expandedDeliveryId, deliveries]);

  const handleChange = (e) => setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  const handlePasswordChange = (e) => setPasswords(prev => ({ ...prev, [e.target.name]: e.target.value }));

  const handleUpdate = async () => {
    try {
      const token = localStorage.getItem("token");
      await axios.put(`${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/update/${user.id}`, formData, {
        headers: { Authorization: `Bearer ${token}` },
      });
      Swal.fire("Success", "Profile updated!", "success");
      localStorage.setItem("user", JSON.stringify({ ...user, ...formData }));
      setUser({ ...user, ...formData });
    } catch {
      Swal.fire("Error", "Failed to update profile.", "error");
    }
  };

  const handleDelete = async () => {
    const confirm = await Swal.fire({
      title: "Delete your account?",
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Yes",
    });
    if (confirm.isConfirmed) {
      try {
        const token = localStorage.getItem("token");
        await axios.delete(`${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/${user.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        localStorage.clear();
        Swal.fire("Deleted", "Account removed.", "success");
        window.location.href = "/";
      } catch {
        Swal.fire("Error", "Delete failed.", "error");
      }
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const uploadedUrl = await mediaUpload(file);
      setFormData(prev => ({ ...prev, image: uploadedUrl }));
      Swal.fire("Success", "Image uploaded.", "success");
    } catch {
      Swal.fire("Error", "Image upload failed.", "error");
    }
  };

  const getLocation = () => {
    navigator.geolocation?.getCurrentPosition(
      async ({ coords }) => {
        const res = await axios.get(
          `https://nominatim.openstreetmap.org/reverse?lat=${coords.latitude}&lon=${coords.longitude}&format=json`
        );
        setFormData(prev => ({ ...prev, address: res.data?.display_name || "" }));
        Swal.fire("Success", "Location fetched!", "success");
      },
      () => Swal.fire("Error", "Geolocation not allowed or failed.", "error")
    );
  };

  const handleLogout = () => {
    localStorage.clear();
    Swal.fire("Logged out", "See you again!", "success");
    window.location.href = "/login";
  };

  const handleChangePassword = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.put(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/update/password/${user.id}`,
        passwords,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      Swal.fire("Success", res.data.message, "success");
      setPasswords({ oldPassword: "", newPassword: "" });
    } catch (err) {
      Swal.fire("Error", err.response?.data?.message || "Failed to change password", "error");
    }
  };

  if (!user) return <div className="p-6">Loading profile...</div>;

  return (
    <div className="max-w-4xl mx-auto p-6 bg-gradient-to-r from-gray-700 to-pink-700 rounded-xl shadow-xl mt-10">
      <div className="flex flex-col items-center">
        <div onClick={() => fileInputRef.current.click()} className="cursor-pointer mb-4">
          <img
            src={formData.image || "https://via.placeholder.com/150?text=Upload+Image"}
            className="w-32 h-32 object-cover rounded-full border-4 shadow-lg"
            alt="Profile"
          />
        </div>
        <input type="file" ref={fileInputRef} onChange={handleImageUpload} className="hidden" />
        <h2 className="text-white text-3xl mb-2">Your Profile</h2>
        <button onClick={handleLogout} className="bg-red-600 text-white px-4 py-2 rounded">
          Logout
        </button>
      </div>

      <div className="bg-white p-6 rounded mt-6 space-y-4">
        <input name="firstName" value={formData.firstName} onChange={handleChange} placeholder="First Name" className="w-full p-2 border rounded" />
        <input name="lastName" value={formData.lastName} onChange={handleChange} placeholder="Last Name" className="w-full p-2 border rounded" />
        <input name="email" value={formData.email} disabled className="w-full p-2 border bg-gray-100" />
        <input name="phone" value={formData.phone} onChange={handleChange} placeholder="Phone" className="w-full p-2 border rounded" />
        <input name="address" value={formData.address} onChange={handleChange} placeholder="Address" className="w-full p-2 border rounded" />
        <button onClick={getLocation} className="text-sm text-blue-600 hover:underline">
          Use Current Location
        </button>

        <div className="flex gap-4">
          <button onClick={handleUpdate} className="bg-blue-600 text-white px-4 py-2 rounded">
            Update Profile
          </button>
          <button onClick={handleDelete} className="bg-red-600 text-white px-4 py-2 rounded">
            Delete Account
          </button>
        </div>

        <div className="pt-4 border-t">
          <h3 className="font-semibold text-gray-700">Change Password</h3>
          <input type="password" name="oldPassword" value={passwords.oldPassword} onChange={handlePasswordChange} placeholder="Old Password" className="w-full p-2 border rounded mt-2" />
          <input type="password" name="newPassword" value={passwords.newPassword} onChange={handlePasswordChange} placeholder="New Password" className="w-full p-2 border rounded mt-2" />
          <button onClick={handleChangePassword} className="bg-blue-600 text-white px-4 py-2 mt-2 rounded">
            Change Password
          </button>
        </div>
      </div>

      <div className="mt-10">
        <h3 className="text-white text-xl mb-4">Delivery History</h3>
        {deliveriesLoading ? (
          <p>Loading...</p>
        ) : (
          deliveries.map((delivery) => (
            <div key={delivery._id} className="bg-white p-4 mb-4 rounded shadow-sm">
              <p><strong>Order ID:</strong> {delivery.orderId}</p>
                        <p><strong>Order Name:</strong> {delivery.orderName}</p>
                        <p><strong>Delivered To:</strong> {delivery.address}</p>
                        <p><strong>Driver:</strong> {delivery.driverName} ({delivery.driverPhone})</p>
                        <p><strong>Status:</strong> {delivery.status}</p>
                        <p><strong>Estimated Time:</strong> {new Date(delivery.estimatedTime).toLocaleString()}</p>
              <div className="flex items-center gap-4 mt-4">
                <img
                  src={delivery.itemImage}
                  alt={delivery.orderName}
                  className="w-20 h-20 object-cover rounded"
                />
                <div>
                  <button
                    className="text-blue-600 hover:underline"
                    onClick={() => handleDriverLocation(delivery._id)}
                  >
                    {expandedDeliveryId === delivery._id ? "" : "View Driver Location"}
                  </button>
                  {expandedDeliveryId === delivery._id && (
                    <div
                      ref={(el) => (mapRefs.current[delivery._id] = el)}
                      className="mt-3"
                      style={{ height: "300px", width: "800px",  }}

                    />
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      
    </div>
  );
}
