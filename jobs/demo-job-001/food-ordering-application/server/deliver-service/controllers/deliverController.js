import Delivery from "../models/delivery.js";
import axios from "axios";
import { checkCustomer, checkRestaurant } from "./authController.js";

export async function addDelivery(req, res) {
    try {
        const newDeliver = new Delivery(req.body);
        await newDeliver.save();
        res.json("Delivery details added successfully");
    } catch (err) {
        res.status(500).json({ error: err });
    }
}

export async function getDelivery(req, res) {
    try {
        if (checkCustomer(req) || checkRestaurant(req)) {
            const result = await Delivery.find({ customerEmail: req.user.email });
            res.json(result);
            return;
        }
        const result = await Delivery.find({ driverId: req.user.id });
        res.json(result);
    } catch (err) {
        res.status(500).json({ error: err });
    }
}

export async function updateDeliveryLocation(req, res) {
    try {
        const { lat, lng } = req.body;

        if (!lat || !lng) {
            return res.status(400).json({ error: "Latitude and longitude are required" });
        }

        const updatedDelivery = await Delivery.findByIdAndUpdate(
            req.params.id,
            { lat, lng },
            { new: true }
        );

        if (!updatedDelivery) {
            return res.status(404).json({ error: "Delivery not found" });
        }

        res.json(updatedDelivery);
    } catch (err) {
        res.status(500).json({ error: err });
    }
}

export async function updateDeliveryStatus(req, res) {
    try {
        const { status } = req.body;

        if (!status) {
            return res.status(400).json({ error: "Status is required" });
        }

        const updatedDelivery = await Delivery.findByIdAndUpdate(
            req.params.id,
            { status },
            { new: true }
        );

        if (!updatedDelivery) {
            return res.status(404).json({ error: "Delivery not found" });
        }

        // Notify order-service to sync delivery status
        const orderServiceUrl = process.env.ORDER_SERVICE_URL || 'http://localhost:3001';
        try {
            await axios.put(`${orderServiceUrl}/api/v1/orders/status/${updatedDelivery.orderId}`, { status });
        } catch (interServiceErr) {
            console.error('Failed to sync order status:', interServiceErr.message);
        }

        res.json(updatedDelivery);
    } catch (err) {
        res.status(500).json({ error: err });
    }
}

export async function getLocation(req, res) {
    try {
        const id = req.params.id;
        const result = await Delivery.findOne({ _id: id });
        res.json(result);
    } catch (err) {
        res.status(500).json({ error: err });
    }
}
