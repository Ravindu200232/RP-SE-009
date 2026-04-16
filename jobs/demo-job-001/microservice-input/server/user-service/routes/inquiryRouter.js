import express from "express";
import { addInquiry, deleteInquiry, getInquiry, updateInquiry } from "../controllers/InquiryController.js";

const inquiryRouter = express.Router();

/**
 * @swagger
 * tags:
 *   name: Inquiries
 *   description: Customer inquiry management
 */

/**
 * @swagger
 * /api/inquiry:
 *   post:
 *     summary: Submit a new inquiry
 *     tags: [Inquiries]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [name, email, message]
 *             properties:
 *               name: { type: string }
 *               email: { type: string, format: email }
 *               message: { type: string }
 *     responses:
 *       201: { description: Inquiry submitted successfully }
 *       400: { description: Validation error }
 */
inquiryRouter.post("/",addInquiry)

/**
 * @swagger
 * /api/inquiry:
 *   get:
 *     summary: Get all inquiries (admin only)
 *     tags: [Inquiries]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of inquiries }
 *       401: { description: Unauthorized }
 */
inquiryRouter.get("/",getInquiry)

/**
 * @swagger
 * /api/inquiry/{id}:
 *   delete:
 *     summary: Delete an inquiry by ID
 *     tags: [Inquiries]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Inquiry ID
 *     responses:
 *       200: { description: Inquiry deleted }
 *       404: { description: Inquiry not found }
 */
inquiryRouter.delete("/:id",deleteInquiry)

/**
 * @swagger
 * /api/inquiry/{id}:
 *   put:
 *     summary: Update an inquiry by ID
 *     tags: [Inquiries]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Inquiry ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               name: { type: string }
 *               email: { type: string, format: email }
 *               message: { type: string }
 *     responses:
 *       200: { description: Inquiry updated }
 *       404: { description: Inquiry not found }
 */
inquiryRouter.put("/:id",updateInquiry)

export  default inquiryRouter;