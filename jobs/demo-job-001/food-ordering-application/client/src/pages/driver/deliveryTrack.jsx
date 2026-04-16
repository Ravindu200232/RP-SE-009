import React, { useEffect, useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";

export function DeliveryTrack() {
  const [deliveries, setDeliveries] = useState([]);
  const token = localStorage.getItem("token");

  useEffect(() => {
    fetchDeliveries();
  }, []);

  const fetchDeliveries = async () => {
    try {
      const res = await axios.get("${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDeliveries(res.data);
    } catch (err) {
      console.error("Failed to fetch deliveries", err);
    }
  };

  const updateStatus = async (id, status) => {
    try {
      await axios.put(
        `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery/update/${id}`,
        { status },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      fetchDeliveries(); // refresh data
    } catch (err) {
      console.error("Failed to update status", err);
    }
  };

  const updateLocation = async (id) => {
    try {
      if (!navigator.geolocation) {
        return alert("Geolocation not supported");
      }

      navigator.geolocation.getCurrentPosition(async (position) => {
        const { latitude, longitude } = position.coords;

        await axios.put(
          `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery/location/${id}`,
          { lat: latitude, lng: longitude },
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        toast.success("Update Location")

        fetchDeliveries(); // refresh data
      });
    } catch (err) {
      console.error("Failed to update location", err);
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Delivery Tracking</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white shadow-md rounded">
          <thead className="bg-gray-100 text-gray-700">
            <tr>
              <th className="py-2 px-4">Order ID</th>
              <th className="py-2 px-4">Status</th>
              <th className="py-2 px-4">Lat</th>
              <th className="py-2 px-4">Lng</th>
              <th className="py-2 px-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.map((delivery) => (
              <tr key={delivery._id} className="border-t">
                <td className="py-2 px-4">{delivery.orderId}</td>
                <td className="py-2 px-4">
                  <select
                    value={delivery.status}
                    onChange={(e) => updateStatus(delivery._id, e.target.value)}
                    className="border rounded px-2 py-1"
                  >
                    <option value="picked up">picked up</option>
                    <option value="on the way">Picked Up</option>
                    <option value="delivered">Delivered</option>
                  </select>
                </td>
                <td className="py-2 px-4">{delivery.lat}</td>
                <td className="py-2 px-4">{delivery.lng}</td>
                <td className="py-2 px-4">
                  <button
                    onClick={() => updateLocation(delivery._id)}
                    className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                  >
                    Update Location
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
