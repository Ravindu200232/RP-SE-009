import Collection from "../models/collection.js";
import Order from "../models/order.js";
import axios from "axios";
import { checkAdmin, checkCustomer, checkHasAccount, checkRestaurant } from "./authController.js";

export async function addOrder(req, res) {
  const data = req.body;

  if (!req.user) {
    return res.status(401).json({ message: "Please login and try again" });
  }

  const createdOrders = [];

  for (const item of data.orderItem) {
    try {
      const product = await Collection.findById(item.key);

      if (!product) {
        return res.status(404).json({ message: `Product with key ${item.key} not found` });
      }

      if (!product.available) {
        return res.status(400).json({ message: `Product with key ${item.key} is not available` });
      }

      const lastOrder = await Order.find().sort({ orderId: -1 }).limit(1);
      const lastId = lastOrder[0]?.orderId?.replace("ORD", "") ?? "0000";
      const nextOrderId = "ORD" + String(parseInt(lastId) + 1 + createdOrders.length).padStart(4, "0");

      const totalAmount = product.price * item.qty;

      const newOrder = new Order({
        email: req.user.email,
        address: req.user.address,
        key: product._id,
        orderId: nextOrderId,
        restaurantId: product.restaurantId,
        ownerId: product.ownerId,
        Item_Id: product._id,
        Item_name: product.name,
        image: product.images[0],
        price: product.price,
        phone: req.user.phone,
        customerName: req.user.firstName + " " + req.user.lastName,
        quantity: item.qty,
        totalAmount: totalAmount,
        status: "pending",
        paymentStatus: "unpaid",
        isApprove: false,
        lat: req.user.lat,
        lng: req.user.lng
      });

      const savedOrder = await newOrder.save();
      createdOrders.push(savedOrder);

    } catch (err) {
      console.error(err);
      return res.status(500).json({ message: "Failed to create order", error: err.message });
    }
  }

  return res.json({
    message: "Orders created successfully",
    orders: createdOrders,
  });
}

export async function getOrder(req, res) {
  try {
    if (checkHasAccount(req)) {
      if (checkAdmin(req)) {
        const result = await Order.find();
        res.json(result);
        return;
      }
      if (checkRestaurant(req)) {
        const result = await Order.find({ ownerId: req.user.id });
        res.json(result);
        return;
      }
      res.status(401).json({ message: "Can't access this task" });
    } else {
      res.status(401).json({ message: "Can't access this task" });
    }
  } catch (err) {
    res.status(500).json({ error: "Internal Server error" || err });
  }
}

export async function deleteOrder(req, res) {
  try {
    const id = req.params.id;
    if (checkHasAccount(req)) {
      if (checkAdmin(req)) {
        await Order.deleteOne({ _id: id });
        res.json({ message: "Order deleted successfully" });
        return;
      }
      await Order.deleteOne({ _id: id, userId: req.user.id });
      res.json({ message: "Order deleted successfully" });
    } else {
      res.status(401).json({ message: "Please login" });
    }
  } catch (err) {
    res.status(500).json({ error: "Internal Server error" || err });
  }
}

export async function getQuote(req, res) {
  const data = req.body;
  const orderInfo = { orderItem: [], totalAmount: 0 };

  for (let i = 0; i < data.orderItem.length; i++) {
    const item = data.orderItem[i];
    try {
      const product = await Collection.findOne({ _id: item.key });

      if (!product) {
        return res.status(404).json({ message: `Product with key ${item.key} not found` });
      }

      if (product.available === false) {
        return res.status(400).json({ message: `Product with key ${item.key} is not available` });
      }

      const quantity = item.qty;
      const itemTotal = product.price * quantity;

      orderInfo.orderItem.push({
        product: {
          key: product._id,
          name: product.name,
          image: product.images[0],
          price: product.price,
          restaurantId: product.restaurantId
        },
        quantity: quantity,
      });

      orderInfo.totalAmount += itemTotal;
    } catch (err) {
      return res.status(500).json({ message: "Something went wrong while processing order quote" });
    }
  }

  return res.json({
    message: "Order quotation",
    total: orderInfo.totalAmount,
    orderItems: orderInfo.orderItem,
  });
}

export async function updateStatus(req, res) {
  try {
    const id = req.params.id;
    const updateData = req.body;

    const updatedOrder = await Order.findOneAndUpdate(
      { orderId: id },
      updateData,
      { new: true }
    );

    if (!updatedOrder) {
      return res.status(404).json({ message: "Order not found" });
    }

    res.json({ message: "Status updated successfully", order: updatedOrder });
  } catch (err) {
    res.status(500).json({ error: "Failed to update order status", details: err });
  }
}

export async function isApprove(req, res) {
  try {
    const id = req.params.id;

    if (checkHasAccount(req)) {
      if (checkAdmin(req)) {
        await Order.updateOne({ _id: id }, { isApprove: true });
        res.json("Order Approved");
        return;
      }
      res.status(401).json({ message: "Can't access this task" });
    } else {
      res.status(401).json({ message: "Can't access this task" });
    }
  } catch (err) {
    res.status(500).json({ err: err });
  }
}
