import mongoose from "mongoose";

const paymentSchema = new mongoose.Schema({
  bookingId: {
    type: String,
    required: true,
  },
  amount: {
    type: Number,
    required: true,
  },
  paymentType: {
    type: String,
    enum: ["Card", "PayPal", "Bank Transfer"],
    required: true,
  },
  cardNumber: {
    type: String,
    required: false,
  },
  expiry: {
    type: String,
    required: false,
  },
  cvv: {
    type: String,
    required: false,
  },
  paymentDate: {
    type: Date,
    default: Date.now,
  },
});

export default mongoose.model("Payment", paymentSchema);
