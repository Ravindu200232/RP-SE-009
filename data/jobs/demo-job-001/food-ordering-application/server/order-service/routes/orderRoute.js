import express from "express";
import { addOrder, deleteOrder, getOrder, getQuote, isApprove, updateStatus } from "../controllers/orderController.js";

const orderRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Orders
 *   description: Order management
 */

/**
 * @swagger
 * /api/v1/orders:
 *   post:
 *     summary: Create a new order
 *     tags: [Orders]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               orderItem:
 *                 type: array
 *                 items:
 *                   type: object
 *                   properties:
 *                     key: { type: string }
 *                     qty: { type: number }
 *     responses:
 *       200: { description: Orders created successfully }
 *       401: { description: Unauthorized }
 */
orderRoute.post("/", addOrder);

/**
 * @swagger
 * /api/v1/orders:
 *   get:
 *     summary: Get orders
 *     tags: [Orders]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of orders }
 */
orderRoute.get("/", getOrder);

/**
 * @swagger
 * /api/v1/orders/delete/{id}:
 *   delete:
 *     summary: Delete an order
 *     tags: [Orders]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Order deleted }
 */
orderRoute.delete("/delete/:id", deleteOrder);

/**
 * @swagger
 * /api/v1/orders/quote:
 *   post:
 *     summary: Get a price quote before ordering
 *     tags: [Orders]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               orderItem:
 *                 type: array
 *                 items:
 *                   type: object
 *                   properties:
 *                     key: { type: string }
 *                     qty: { type: number }
 *     responses:
 *       200: { description: Quote with total amount }
 */
orderRoute.post("/quote", getQuote);

/**
 * @swagger
 * /api/v1/orders/status/{id}:
 *   put:
 *     summary: Update order or payment status
 *     tags: [Orders]
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
 *             properties:
 *               status: { type: string, enum: [pending, confirmed, preparing, dispatched, delivered] }
 *               paymentStatus: { type: string, enum: [unpaid, paid] }
 *     responses:
 *       200: { description: Status updated }
 *       404: { description: Order not found }
 */
orderRoute.put("/status/:id", updateStatus);

/**
 * @swagger
 * /api/v1/orders/isApprove/{id}:
 *   put:
 *     summary: Approve an order (admin only)
 *     tags: [Orders]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Order approved }
 */
orderRoute.put("/isApprove/:id", isApprove);

export default orderRoute;
