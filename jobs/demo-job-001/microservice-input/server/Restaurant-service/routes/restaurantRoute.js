import express from 'express';
import { closeShop, createRestaurant, deleteRestaurant, getOne, getRestaurant, isOpen, updateRestaurant, verification } from '../controllers/resturantsController.js';

const restaurantRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Restaurants
 *   description: Restaurant management
 */

/**
 * @swagger
 * /api/v1/restaurant:
 *   post:
 *     summary: Create a new restaurant
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [name, address, phone]
 *             properties:
 *               name: { type: string }
 *               ownerName: { type: string }
 *               address: { type: string }
 *               phone: { type: string }
 *               description: { type: string }
 *     responses:
 *       201: { description: Restaurant created }
 *       401: { description: Unauthorized }
 */
restaurantRoute.post("/", createRestaurant);

/**
 * @swagger
 * /api/v1/restaurant:
 *   get:
 *     summary: Get all restaurants
 *     tags: [Restaurants]
 *     responses:
 *       200: { description: List of restaurants }
 */
restaurantRoute.get("/", getRestaurant);

/**
 * @swagger
 * /api/v1/restaurant/getOne/{id}:
 *   get:
 *     summary: Get a single restaurant by ID (used by Notification Service)
 *     tags: [Restaurants]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant details }
 *       404: { description: Restaurant not found }
 */
restaurantRoute.get("/getOne/:id", getOne);

/**
 * @swagger
 * /api/v1/restaurant/update/{id}:
 *   put:
 *     summary: Update a restaurant
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant updated }
 */
restaurantRoute.put("/update/:id", updateRestaurant);

/**
 * @swagger
 * /api/v1/restaurant/delete/{id}:
 *   delete:
 *     summary: Delete a restaurant (admin only)
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant deleted }
 */
restaurantRoute.delete("/delete/:id", deleteRestaurant);

/**
 * @swagger
 * /api/v1/restaurant/isOpen/{id}:
 *   post:
 *     summary: Mark restaurant as open
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant opened }
 */
restaurantRoute.post("/isOpen/:id", isOpen);

/**
 * @swagger
 * /api/v1/restaurant/isClose/{id}:
 *   post:
 *     summary: Mark restaurant as closed
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant closed }
 */
restaurantRoute.post("/isClose/:id", closeShop);

/**
 * @swagger
 * /api/v1/restaurant/isVerify/{id}:
 *   post:
 *     summary: Verify a restaurant (admin only)
 *     tags: [Restaurants]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: Restaurant verified }
 */
restaurantRoute.post("/isVerify/:id", verification);

export default restaurantRoute;
