import express from "express";
import { EmailSender } from "../controllers/notificationSender.js";

const notificationRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Notifications
 *   description: Email notification service
 */

/**
 * @swagger
 * /api/v1/notification:
 *   post:
 *     summary: Send delivery notification emails to driver and customer
 *     description: Fetches restaurant info from Restaurant Service, then emails both driver and customer
 *     tags: [Notifications]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [orderId, driverEmail, customerEmail, restaurantId]
 *             properties:
 *               orderId: { type: string }
 *               driverId: { type: string }
 *               driverName: { type: string }
 *               driverPhone: { type: string }
 *               driverEmail: { type: string, format: email }
 *               customerEmail: { type: string, format: email }
 *               address: { type: string }
 *               phone: { type: string }
 *               status: { type: string }
 *               estimatedTime: { type: string, format: date-time }
 *               lat: { type: number }
 *               lng: { type: number }
 *               itemName: { type: string }
 *               qty: { type: number }
 *               totalPrice: { type: number }
 *               restaurantId: { type: string, description: Fetches restaurant info from Restaurant Service }
 *     responses:
 *       200: { description: Emails sent successfully }
 *       500: { description: Failed to send email }
 */
notificationRoute.post("/", EmailSender);

export default notificationRoute;
