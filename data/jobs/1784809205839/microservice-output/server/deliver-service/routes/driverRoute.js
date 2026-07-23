import express from "express";
import { createDriver, deleteDriver, driverLogin, getDriver, updateDriver } from "../controllers/driverController.js";

const driverRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Drivers
 *   description: Delivery driver management
 */

/**
 * @swagger
 * /api/v1/driver/login:
 *   post:
 *     summary: Driver login
 *     tags: [Drivers]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email, password]
 *             properties:
 *               email: { type: string, format: email }
 *               password: { type: string }
 *     responses:
 *       200: { description: Login successful, returns JWT token }
 *       401: { description: Invalid credentials }
 */
driverRoute.post("/login",driverLogin);

/**
 * @swagger
 * /api/v1/driver:
 *   post:
 *     summary: Register a new driver
 *     tags: [Drivers]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [name, email, password, phone]
 *             properties:
 *               name: { type: string }
 *               email: { type: string, format: email }
 *               password: { type: string, minLength: 6 }
 *               phone: { type: string }
 *               vehicleType: { type: string }
 *               licenseNumber: { type: string }
 *     responses:
 *       201: { description: Driver registered successfully }
 *       400: { description: Validation error }
 */
driverRoute.post("/",createDriver);

/**
 * @swagger
 * /api/v1/driver:
 *   get:
 *     summary: Get all drivers (admin only)
 *     tags: [Drivers]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of drivers }
 *       401: { description: Unauthorized }
 */
driverRoute.get("/",getDriver);

/**
 * @swagger
 * /api/v1/driver/{id}:
 *   put:
 *     summary: Update driver information
 *     tags: [Drivers]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Driver ID
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               name: { type: string }
 *               phone: { type: string }
 *               vehicleType: { type: string }
 *               licenseNumber: { type: string }
 *     responses:
 *       200: { description: Driver updated }
 *       404: { description: Driver not found }
 */
driverRoute.put("/:id",updateDriver);

/**
 * @swagger
 * /api/v1/driver/{id}:
 *   delete:
 *     summary: Delete a driver by ID
 *     tags: [Drivers]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *         description: Driver ID
 *     responses:
 *       200: { description: Driver deleted }
 *       404: { description: Driver not found }
 */
driverRoute.delete("/:id",deleteDriver);

export default driverRoute

