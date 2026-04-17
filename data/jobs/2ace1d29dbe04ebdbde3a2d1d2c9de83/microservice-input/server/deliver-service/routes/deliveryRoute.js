import express from 'express';
import { addDelivery, getDelivery, getLocation, updateDeliveryLocation, updateDeliveryStatus } from '../controllers/deliverController.js';

const deliveryRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Deliveries
 *   description: Delivery tracking management
 */

/**
 * @swagger
 * /api/v1/delivery:
 *   post:
 *     summary: Add a new delivery
 *     tags: [Deliveries]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               driverId: { type: string }
 *               driverName: { type: string }
 *               customerEmail: { type: string }
 *               orderId: { type: string }
 *               orderName: { type: string }
 *               address: { type: string }
 *               lat: { type: number }
 *               lng: { type: number }
 *     responses:
 *       200: { description: Delivery added }
 */
deliveryRoute.post("/", addDelivery);

/**
 * @swagger
 * /api/v1/delivery:
 *   get:
 *     summary: Get deliveries for the current user
 *     tags: [Deliveries]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of deliveries }
 */
deliveryRoute.get("/", getDelivery);

/**
 * @swagger
 * /api/v1/delivery/location/{id}:
 *   put:
 *     summary: Update delivery GPS location
 *     tags: [Deliveries]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [lat, lng]
 *             properties:
 *               lat: { type: number }
 *               lng: { type: number }
 *     responses:
 *       200: { description: Location updated }
 */
deliveryRoute.put("/location/:id", updateDeliveryLocation);

/**
 * @swagger
 * /api/v1/delivery/update/{id}:
 *   put:
 *     summary: Update delivery status (also syncs to Order Service)
 *     tags: [Deliveries]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [status]
 *             properties:
 *               status: { type: string, enum: [picked up, on the way, delivered] }
 *     responses:
 *       200: { description: Status updated }
 */
deliveryRoute.put("/update/:id", updateDeliveryStatus);

/**
 * @swagger
 * /api/v1/delivery/loc/{id}:
 *   get:
 *     summary: Get current delivery location
 *     tags: [Deliveries]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Delivery location data }
 */
deliveryRoute.get("/loc/:id", getLocation);

export default deliveryRoute;
