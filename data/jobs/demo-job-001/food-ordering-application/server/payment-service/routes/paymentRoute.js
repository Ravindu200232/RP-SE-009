import express from "express";
import { getAllPayments, makePayment } from "../controllers/paymentController.js";

const paymentRouter = express.Router();

/**
 * @swagger
 * tags:
 *   name: Payments
 *   description: Payment processing
 */

/**
 * @swagger
 * /api/payment:
 *   post:
 *     summary: Process a payment (calls Order Service to update payment status)
 *     tags: [Payments]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [bookingId, amount, paymentType, cardNumber, expiry, cvv]
 *             properties:
 *               bookingId: { type: string, description: Order ID }
 *               amount: { type: number }
 *               paymentType: { type: string, enum: [Card, PayPal, Bank Transfer] }
 *               cardNumber: { type: string }
 *               expiry: { type: string }
 *               cvv: { type: string }
 *     responses:
 *       200: { description: Payment successful }
 *       500: { description: Payment processing error }
 */
paymentRouter.post("/", makePayment);

/**
 * @swagger
 * /api/payment:
 *   get:
 *     summary: Get all payments (admin only)
 *     tags: [Payments]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of payments - sensitive data excluded }
 *       403: { description: Access denied }
 */
paymentRouter.get("/", getAllPayments);

export default paymentRouter;
