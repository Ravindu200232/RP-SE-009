import mongoose from "mongoose";

const orderSchema = new mongoose.Schema({
  // Customer Info
  email: {
    type: String,
    required: true,
  },
  customerName : {
    type : String,
    required : true
  },
  phone : {
    type : String,
    required : true
  },
  address: {
    type: String,
    required: true,
  },

  // Unique Order ID
  orderId: {
    type: String,
    required: true,
    unique: true,
  },

  // Product Info (flat structure per item)
  key: {
    type: String,  // Product ID
    required: true,
  },
  Item_Id: {
    type: String,
    required: true,
  },
  Item_name: {
    type: String,
    required: true,
  },
  image: {
    type: String,
    required: true,
  },
  price: {
    type: Number,
    required: true,
  },
  quantity: {
    type: Number,
    required: true,
  },

  // Restaurant Info
  restaurantId: {
    type: String,
    ref: "Restaurant",
    required: true,
  },
  ownerId: {
    type: String,
    required: true,
  },

  // Order Status & Tracking
  status: {
    type: String,
    enum: ["pending", "confirmed", "preparing", "dispatched", "delivered"],
    default: "pending",
    required: true,
  },
  deliveryId: {
    type: String, // Optional: Delivery agent ID
  },

  // Pricing & Payment
  totalAmount: {
    type: Number,
    required: true,
  },
  paymentStatus: {
    type: String,
    enum: ["unpaid", "paid"],
    default: "unpaid",
  },

  // Admin Approval
  isApprove: {
    type: Boolean,
    default: false,
    required: true,
  },

  // Timestamp
  createdAt: {
    type: Date,
    default: Date.now,
    required: true,
  },
  lat: {
    type: Number,
    required:false
},
lng: {
    type: Number,
    required:false
   
},
});

const Order = mongoose.model("Order", orderSchema);

export default Order;
