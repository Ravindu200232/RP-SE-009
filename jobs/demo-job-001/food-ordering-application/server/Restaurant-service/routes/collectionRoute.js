import express from 'express'
import { approveItem, createCollection, deleteCollection, getAll, getOne, getRestaurantCollection, updateCollection } from '../controllers/collectionController.js';

const collectionRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Collections
 *   description: Restaurant menu collection management
 */

/**
 * @swagger
 * /api/v1/collection:
 *   post:
 *     summary: Create a new menu collection item
 *     tags: [Collections]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [name, price, restaurantId]
 *             properties:
 *               name: { type: string }
 *               price: { type: number }
 *               restaurantId: { type: string }
 *               description: { type: string }
 *               image: { type: string }
 *               category: { type: string }
 *     responses:
 *       201: { description: Collection item created }
 *       401: { description: Unauthorized }
 */
collectionRoute.post("/",createCollection);

/**
 * @swagger
 * /api/v1/collection/getAll/{id}:
 *   get:
 *     summary: Get all menu collections for a specific restaurant
 *     tags: [Collections]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Restaurant ID
 *     responses:
 *       200: { description: List of collection items for the restaurant }
 *       404: { description: Restaurant not found }
 */
collectionRoute.get("/getAll/:id",getRestaurantCollection);

/**
 * @swagger
 * /api/v1/collection/update/{id}:
 *   put:
 *     summary: Update a menu collection item
 *     tags: [Collections]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Collection item ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               name: { type: string }
 *               price: { type: number }
 *               description: { type: string }
 *               image: { type: string }
 *               category: { type: string }
 *     responses:
 *       200: { description: Collection item updated }
 *       404: { description: Item not found }
 */
collectionRoute.put("/update/:id",updateCollection);

/**
 * @swagger
 * /api/v1/collection/delete/{id}:
 *   delete:
 *     summary: Delete a menu collection item
 *     tags: [Collections]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Collection item ID
 *     responses:
 *       200: { description: Collection item deleted }
 *       404: { description: Item not found }
 */
collectionRoute.delete("/delete/:id",deleteCollection);

/**
 * @swagger
 * /api/v1/collection:
 *   get:
 *     summary: Get all menu collection items
 *     tags: [Collections]
 *     responses:
 *       200: { description: List of all collection items }
 */
collectionRoute.get("/",getAll);

/**
 * @swagger
 * /api/v1/collection/isApprove/{id}:
 *   post:
 *     summary: Approve a menu collection item (admin only)
 *     tags: [Collections]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Collection item ID
 *     responses:
 *       200: { description: Collection item approved }
 *       401: { description: Unauthorized }
 */
collectionRoute.post("/isApprove/:id",approveItem);

/**
 * @swagger
 * /api/v1/collection/getOne/{id}:
 *   get:
 *     summary: Get a single menu collection item by ID
 *     tags: [Collections]
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Collection item ID
 *     responses:
 *       200: { description: Collection item details }
 *       404: { description: Item not found }
 */
collectionRoute.get("/getOne/:id",getOne)

export default collectionRoute