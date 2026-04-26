import React, { useEffect, useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";

export function AdminPayment() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  const backendUrl = import.meta.env.VITE_BACKEND_URL;

  useEffect(() => {
    const fetchPayments = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await axios.get(`${import.meta.env.VITE_PAYMENT_SERVICE_URL}/api/payment`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        setPayments(res.data);
      } catch (err) {
        console.error(err);
        toast.error("Failed to fetch payment records.");
      } finally {
        setLoading(false);
      }
    };

    fetchPayments();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-primary">
        Loading payments...
      </div>
    );
  }

  return (
    <div className="min-h-screen  text-primary p-6">
      <h1 className="text-3xl font-bold text-primary mb-6">
        All Payment Records
      </h1>

      {payments.length === 0 ? (
        <p className="text-center text-red-500">No payments found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white rounded-lg shadow-md">
            <thead className="bg-primary text-white">
              <tr>
                <th className="p-3 text-left">Booking ID</th>
                <th className="p-3 text-left">Amount</th>
                <th className="p-3 text-left">Payment Type</th>
                <th className="p-3 text-left">Date</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <tr key={payment._id} className="border-t hover:bg-gray-100">
                  <td className="p-3">{payment.bookingId}</td>
                  <td className="p-3">Rs.{payment.amount.toFixed(2)}</td>
                  <td className="p-3">{payment.paymentType}</td>
                  <td className="p-3">
                    {new Date(payment.paymentDate).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
