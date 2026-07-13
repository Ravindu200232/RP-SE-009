import React, { useEffect, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";
import { toast } from "react-toastify";

const AdminBookingPage = () => {
  const [bookingData, setBookingData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState({});
  const [expandedDescriptions, setExpandedDescriptions] = useState({});

  useEffect(() => {
    const fetchBookingData = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setBookingData(response.data || []);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchBookingData();
  }, []);

  const handleApproveOrder = async (orderId) => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");

      await axios.put(
        `${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders/isApprove/${orderId}`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      setBookingData((prevData) =>
        prevData.map((order) =>
          order.orderId === orderId ? { ...order, isApprove: true } : order
        )
      );

      toast.success("Order approved successfully");
    } catch (error) {
      console.error("Error approving order:", error);
      toast.error("Failed to approve order");
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
        await axios.delete(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders/delete/${orderId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });

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
                <th className="px-4 py-3">Approval</th>
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
                    <td className="px-4 py-3">
                      {order.isApprove ? (
                        <span className="text-green-600 font-semibold">Approved</span>
                      ) : (
                        <span className="text-yellow-600 font-medium">Pending</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="text-blue-500 underline"
                        onClick={() => toggleDescription(order.orderId)}
                      >
                        {expandedDescriptions[order.orderId] ? "Hide" : "Show"} Description
                      </button>
                    </td>
                    <td className="px-4 py-3 text-center space-x-2">
                      <button
                        onClick={() => handleApproveOrder(order.orderId)}
                        className={`px-3 py-1 rounded text-xs ${
                          order.isApprove ? "bg-green-500 text-white" : "bg-gray-300 text-black"
                        }`}
                        disabled={order.isApprove}
                      >
                        {order.isApprove ? "Approved" : "Approve"}
                      </button>
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
                      <td colSpan="7" className="px-4 py-3 bg-gray-50 italic flex flex-col">
                        <p>Address : {order.address || "N/A"}</p>
                        <p>Customer Name : {order.customerName || "N/A"}</p>
                        <p>Phone : {order.phone || "N/A"}</p>
                        <p>Email : {order.email || "N/A"}</p>
                      </td>
                    </tr>
                  )}

                  {expandedRows[order.orderId] && (
                    <tr>
                      <td colSpan="7" className="px-4 py-3 bg-gray-100">
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
};

export default AdminBookingPage;
