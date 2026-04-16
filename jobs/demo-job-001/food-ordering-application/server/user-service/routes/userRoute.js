import express from 'express';
import {
  blockorUnblockUser, changePassword, createUser, deleteUser,
  getOneUser, getUsers, loginWithGoogle, sendOTP, updateUser, userLogin, verifyOTP
} from '../controllers/userController.js';

const userRoute = express.Router();

/**
 * @swagger
 * tags:
 *   name: Users
 *   description: User management and authentication
 */

/**
 * @swagger
 * /api/v1/users:
 *   post:
 *     summary: Register a new user
 *     tags: [Users]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [firstName, lastName, email, password, role]
 *             properties:
 *               firstName: { type: string }
 *               lastName: { type: string }
 *               email: { type: string, format: email }
 *               password: { type: string, minLength: 6 }
 *               role: { type: string, enum: [customer, restaurant, delivery, admin] }
 *               phone: { type: string }
 *               address: { type: string }
 *     responses:
 *       201: { description: User created successfully }
 *       400: { description: Validation error }
 */
userRoute.post('/', createUser);

/**
 * @swagger
 * /api/v1/users/login:
 *   post:
 *     summary: Login user
 *     tags: [Users]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email, password]
 *             properties:
 *               email: { type: string }
 *               password: { type: string }
 *     responses:
 *       200: { description: Login successful, returns JWT token }
 *       401: { description: Invalid credentials }
 */
userRoute.post('/login', userLogin);

/**
 * @swagger
 * /api/v1/users:
 *   get:
 *     summary: Get all users (admin only)
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200: { description: List of users }
 *       401: { description: Unauthorized }
 */
userRoute.get('/', getUsers);

/**
 * @swagger
 * /api/v1/users/block/{email}:
 *   put:
 *     summary: Block or unblock a user (admin only)
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: email
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: User blocked/unblocked }
 *       401: { description: Unauthorized }
 */
userRoute.put('/block/:email', blockorUnblockUser);

/**
 * @swagger
 * /api/v1/users/oneuser/{id}:
 *   get:
 *     summary: Get a single user by ID
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: User details }
 *       404: { description: User not found }
 */
userRoute.get('/oneuser/:id', getOneUser);

/**
 * @swagger
 * /api/v1/users/update/{id}:
 *   put:
 *     summary: Update user details
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: User updated }
 */
userRoute.put('/update/:id', updateUser);

/**
 * @swagger
 * /api/v1/users/update/password/{id}:
 *   put:
 *     summary: Change user password
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
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
 *               oldPassword: { type: string }
 *               newPassword: { type: string }
 *     responses:
 *       200: { description: Password changed }
 */
userRoute.put('/update/password/:id', changePassword);

/**
 * @swagger
 * /api/v1/users/{id}:
 *   delete:
 *     summary: Delete a user
 *     tags: [Users]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: User deleted }
 */
userRoute.delete('/:id', deleteUser);

/**
 * @swagger
 * /api/v1/users/google:
 *   post:
 *     summary: Login with Google
 *     tags: [Users]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               token: { type: string, description: Google OAuth token }
 *     responses:
 *       200: { description: Login successful }
 */
userRoute.post('/google', loginWithGoogle);

/**
 * @swagger
 * /api/v1/users/sendOTP:
 *   get:
 *     summary: Send OTP to email for verification
 *     tags: [Users]
 *     parameters:
 *       - in: query
 *         name: email
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200: { description: OTP sent }
 */
userRoute.get('/sendOTP', sendOTP);

/**
 * @swagger
 * /api/v1/users/verifyOTP:
 *   post:
 *     summary: Verify OTP
 *     tags: [Users]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               email: { type: string }
 *               otp: { type: string }
 *     responses:
 *       200: { description: OTP verified }
 *       400: { description: Invalid OTP }
 */
userRoute.post('/verifyOTP', verifyOTP);

export default userRoute;
