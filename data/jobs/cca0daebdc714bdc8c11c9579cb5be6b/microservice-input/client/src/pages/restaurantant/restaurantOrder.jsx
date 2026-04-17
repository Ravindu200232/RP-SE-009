import axios from "axios";
import React, { useEffect, useState } from "react";
import toast from "react-hot-toast";
import Swal from "sweetalert2";

export default function RestaurantOrder() {
  const [bookingData, setBookingData] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState({});
  const [expandedDescriptions, setExpandedDescriptions] = useState({});

  useEffect(() => {
    const fetchBookingData = async () => {
      try {
        const token = localStorage.getItem("token");

        const [ordersResponse, driversResponse] = await Promise.all([
          axios.get(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          axios.get(`${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/driver`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        setBookingData(ordersResponse.data || []);
        setDrivers(driversResponse.data || []);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchBookingData();
  }, []);

  const handleStatusChange = async (orderId, newStatus) => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");

      await axios.put(
        `${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders/status/${orderId}`,
        { status: newStatus },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );

      setBookingData((prevData) =>
        prevData.map((order) =>
          order.orderId === orderId ? { ...order, status: newStatus } : order
        )
      );

      toast.success(`Order status updated to ${newStatus}`);

      if (newStatus === "confirmed") {
        const order = bookingData.find((o) => o.orderId === orderId);
        const driverId = order?.assignedDriver;

        if (!driverId) {
          toast.error("Please select a driver before confirming.");
          return;
        }

       

       

        await axios.post(
          `${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/delivery`,
          {
            orderId,
            driverId,
            driverName: drivers.find((driver) => driver._id === driverId)?.firstName + " " + drivers.find((driver) => driver._id === driverId)?.lastName || "N/A",
            driverPhone: drivers.find((driver) => driver._id === driverId)?.phone || "N/A",
            status: "picked up",
            driverEmail : drivers.find((driver) => driver._id === driverId)?.email || "N/A",
            customerEmail: order?.email,
            address: order?.address,
            phone: order?.phone,
            estimatedTime: new Date(Date.now() + 30 * 60 * 1000), // e.g., 30 mins from now
            lat: order?.lat || 0,
            lng: order?.lng || 0,
            timestamp: new Date(),
            orderName : order?.Item_name,
            itemImage : order?.image,
            price : order?.price,
            total : order?.totalAmount,
            qty : order?.quantity,


             
          },
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );


        await axios.post(
          `${import.meta.env.VITE_NOTIFICATION_SERVICE_URL}/api/v1/notification`,
          {
            orderId,
            driverId,
            driverName: drivers.find((driver) => driver._id === driverId)?.firstName + " " + drivers.find((driver) => driver._id === driverId)?.lastName || "N/A",
            driverPhone: drivers.find((driver) => driver._id === driverId)?.phone || "N/A",
            status: "picked up",
            driverEmail : drivers.find((driver) => driver._id === driverId)?.email || "N/A",
            customerEmail: order?.email,
            address: order?.address,
            phone: order?.phone,
            estimatedTime: new Date(Date.now() + 30 * 60 * 1000), // e.g., 30 mins from now
            lat: order?.lat || 0,
            lng: order?.lng || 0,
            itemName : order?.Item_name,
            qty: order?.quantity,
            totalPrice : order?.totalAmount,
            restaurantId : order?.restaurantId,
            timestamp: new Date(),
             
          },
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        

        toast.success("Delivery info saved to database.");
      }
    } catch (error) {
      console.error("Error updating status or saving delivery:", error);
      toast.error("Failed to update status or assign delivery.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteOrder = async (orderId) => {
    const result = await Swal.fire({
      title: "Are you sure?",
      text: "You won't be able to revert this!",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#d33",
      cancelButtonColor: "#3085d6",
      confirmButtonText: "Yes, delete it!",
    });

    if (result.isConfirmed) {
      try {
        setLoading(true);
        const token = localStorage.getItem("token");
        await axios.delete(
          `${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders/delete/${orderId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        setBookingData((prevData) =>
          prevData.filter((order) => order._id !== orderId)
        );

        Swal.fire("Deleted!", "Order has been deleted.", "success");
      } catch (error) {
        console.error("Error deleting order:", error);
        Swal.fire("Error!", "Failed to delete order.", "error");
      } finally {
        setLoading(false);
      }
    }
  };

  const toggleRow = (orderId) => {
    setExpandedRows((prev) => ({
      ...prev,
      [orderId]: !prev[orderId],
    }));
  };

  const toggleDescription = (orderId) => {
    setExpandedDescriptions((prev) => ({
      ...prev,
      [orderId]: !prev[orderId],
    }));
  };

  return (
    <div className="w-full h-full p-6 flex flex-col items-center bg-secondary text-black">
      <h1 className="text-3xl font-bold text-gray-700 mb-6">Order Management</h1>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="w-16 h-16 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm text-left text-gray-600">
            <thead className="bg-primary text-white">
              <tr>
                <th className="px-4 py-3">Order ID</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Order Date</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Count</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Driver</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bookingData.map((order) => (
                <React.Fragment key={order.orderId}>
                  <tr className="bg-white border-b hover:bg-gray-100">
                    <td className="px-4 py-3">{order.orderId}</td>
                    <td className="px-4 py-3">{order.email}</td>
                    <td className="px-4 py-3">
                      {order.createdAt
                        ? new Date(order.createdAt).toLocaleDateString()
                        : "N/A"}
                    </td>
                    <td className="px-4 py-3">Rs.{order.totalAmount}</td>
                    <td className="px-4 py-3">{order.quantity}</td>
                    <td className="px-4 py-3 capitalize">{order.status}</td>
                    <td className="px-4 py-3">
                      <select
                        value={order.assignedDriver || ""}
                        onChange={(e) => {
                          const updatedDriverId = e.target.value;
                          setBookingData((prevData) =>
                            prevData.map((o) =>
                              o.orderId === order.orderId
                                ? { ...o, assignedDriver: updatedDriverId }
                                : o
                            )
                          );
                        }}
                        className="border p-1 rounded text-sm"
                      >
                        <option value="">Select Driver</option>
                        {drivers.map((driver) => (
                          <option key={driver._id} value={driver._id}>
                            {driver.firstName} {driver.lastName}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="text-blue-500 underline"
                        onClick={() => toggleDescription(order.orderId)}
                      >
                        {expandedDescriptions[order.orderId]
                          ? "Hide"
                          : "Show"}{" "}
                        Description
                      </button>
                    </td>
                    <td className="px-4 py-3 text-center space-x-2">
                      <select
                        value={order.status}
                        onChange={(e) =>
                          handleStatusChange(order.orderId, e.target.value)
                        }
                        className="px-2 py-1 text-xs rounded border border-gray-300"
                      >
                        <option value="pending">Pending</option>
                        <option value="confirmed">Confirmed</option>
                        <option value="preparing">Preparing</option>
                        <option value="dispatched">Dispatched</option>
                        <option value="delivered">Delivered</option>
                      </select>
                      <button
                        onClick={() => toggleRow(order.orderId)}
                        className="px-3 py-1 bg-indigo-500 rounded text-white text-xs"
                      >
                        {expandedRows[order.orderId] ? "Hide Items" : "View Items"}
                      </button>
                      <button
                        onClick={() => handleDeleteOrder(order._id)}
                        className="px-3 py-1 bg-red-500 rounded text-white text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>

                  {expandedDescriptions[order.orderId] && (
                    <tr>
                      <td colSpan="8" className="px-4 py-3 bg-gray-50 italic">
                        <p>Address: {order.address || "N/A"}</p>
                        <p>Customer Name: {order.customerName || "N/A"}</p>
                        <p>Phone: {order.phone || "N/A"}</p>
                      </td>
                    </tr>
                  )}

                  {expandedRows[order.orderId] && (
                    <tr>
                      <td colSpan="8" className="px-4 py-3 bg-gray-100">
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                          <div className="border p-3 rounded-lg bg-white text-center">
                            <img
                              src={order.image || "/default-product.jpg"}
                              alt={order.Item_name || "Product"}
                              className="w-20 h-20 mx-auto object-cover rounded mb-2"
                            />
                            <div className="font-semibold">{order.Item_name}</div>
                            <div>Quantity: {order.quantity}</div>
                            <div>Price: Rs.{order.price}</div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
