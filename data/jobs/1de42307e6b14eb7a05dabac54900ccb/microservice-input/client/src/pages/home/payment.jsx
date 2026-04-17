import { useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";

export function Payment() {
  const location = useLocation();
  const navigate = useNavigate();
  const { amount, bookingIds } = location.state || {};
  const [paymentType, setPaymentType] = useState("Card");
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");

  console.log(location.state.bookingIds)

  const validateCardInputs = () => {
    const cardPattern = /^\d{16}$/;
    const expiryPattern = /^(0[1-9]|1[0-2])\/\d{2}$/;
    const cvvPattern = /^\d{3}$/;

    if (!cardPattern.test(cardNumber.replace(/\s/g, ""))) {
      toast.error("Invalid card number");
      return false;
    }
    if (!expiryPattern.test(expiry)) {
      toast.error("Invalid expiry (MM/YY)");
      return false;
    }
    if (!cvvPattern.test(cvv)) {
      toast.error("Invalid CVV");
      return false;
    }

    return true;
  };

  const handlePayment = async () => {
    if (paymentType === "Card" && !validateCardInputs()) {
      return;
    }
  
    try {
      const token = localStorage.getItem("token");
  
      // Divide total amount evenly and round to 2 decimals
      const perBookingAmount = parseFloat((amount / bookingIds.length).toFixed(2));
  
      // Make separate requests for each bookingId
      for (const bookingId of bookingIds) {
        await axios.post(
          `${import.meta.env.VITE_PAYMENT_SERVICE_URL}/api/payment`,
          {
            bookingId,
            amount: perBookingAmount,
            paymentType,
            cardNumber,
            expiry,
            cvv,
          },
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
      }
  
      toast.success("Payment successful!");
      navigate("/"); // 👈 Redirect after all successful
    } catch (err) {
      console.error(err);
      toast.error("Payment failed.");
    }
  };
  

  return (
    <div className="min-h-screen bg-primary p-6 flex flex-col items-center">
      <h1 className="text-3xl font-bold text-accent mb-4">Payment</h1>

      <div className="bg-white rounded-lg shadow-md p-6 w-full max-w-md">
        <p className="text-lg mb-2">
          <strong>Total Amount:</strong> Rs.{amount?.toFixed(2)}
        </p>

        <div className="mb-4">
          <label className="block font-semibold mb-1">Payment Type</label>
          <select
            value={paymentType}
            onChange={(e) => setPaymentType(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded"
          >
            <option value="Card">Card</option>
            <option value="PayPal">PayPal</option>
            <option value="Bank Transfer">Bank Transfer</option>
          </select>
        </div>

        {paymentType === "Card" && (
          <div className="space-y-4">
            <div>
              <label className="block font-semibold mb-1">Card Number</label>
              <input
                type="text"
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className="w-full p-2 border border-gray-300 rounded"
                placeholder="1234567812345678"
                maxLength={16}
              />
            </div>

            <div className="flex space-x-4">
              <div className="w-1/2">
                <label className="block font-semibold mb-1">
                  Expiry (MM/YY)
                </label>
                <input
                  type="text"
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded"
                  placeholder="MM/YY"
                  maxLength={5}
                />
              </div>

              <div className="w-1/2">
                <label className="block font-semibold mb-1">CVV</label>
                <input
                  type="password"
                  value={cvv}
                  onChange={(e) => setCvv(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded"
                  placeholder="123"
                  maxLength={3}
                />
              </div>
            </div>
          </div>
        )}

        <button
          onClick={handlePayment}
          className="mt-6 w-full bg-accent text-white py-2 rounded hover:bg-accent-dark transition"
        >
          Pay Now
        </button>

        <button
          onClick={() => navigate(-1)}
          className="mt-4 w-full bg-gray-300 text-gray-700 py-2 rounded hover:bg-gray-400 transition"  >
            Cancel
          </button>
      </div>
    </div>
  );
}
