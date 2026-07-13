import express from "express";
import { addReview, approveReview, deleteReview, disApproveReview, getReview } from "../controllers/reviewController.js";

const reviewRouter = express.Router();

/**
 * @swagger
 * tags:
 *   name: Reviews
 *   description: Restaurant review management
 */

/**
 * @swagger
 * /api/v1/reviews:
 *   post:
 *     summary: Add a new review for a restaurant
 *     tags: [Reviews]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [restaurantId, rating, comment]
 *             properties:
 *               restaurantId: { type: string }
 *               rating: { type: number, minimum: 1, maximum: 5 }
 *               comment: { type: string }
 *               customerName: { type: string }
 *     responses:
 *       201: { description: Review added successfully }
 *       400: { description: Validation error }
 */
reviewRouter.post("/",addReview);

/**
 * @swagger
 * /api/v1/reviews:
 *   get:
 *     summary: Get all reviews (admin only)
 *     tags: [Reviews]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of all reviews }
 *       401: { description: Unauthorized }
 */
reviewRouter.get("/",getReview);

/**
 * @swagger
 * /api/v1/reviews/delete/{id}:
 *   delete:
 *     summary: Delete a review by ID
 *     tags: [Reviews]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Review ID
 *     responses:
 *       200: { description: Review deleted }
 *       404: { description: Review not found }
 */
reviewRouter.delete("/delete/:id",deleteReview);

/**
 * @swagger
 * /api/v1/reviews/approve/{id}:
 *   put:
 *     summary: Approve a review (admin only)
 *     tags: [Reviews]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Review ID
 *     responses:
 *       200: { description: Review approved }
 *       404: { description: Review not found }
 */
reviewRouter.put("/approve/:id",approveReview);

/**
 * @swagger
 * /api/v1/reviews/{key}:
 *   get:
 *     summary: Disapprove a review by key (admin only)
 *     tags: [Reviews]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: key
 *         required: true
 *         schema: { type: string }
 *         description: Review key or ID to disapprove
 *     responses:
 *       200: { description: Review disapproved }
 *       404: { description: Review not found }
 */
reviewRouter.get("/:key",disApproveReview)



export default reviewRouter;