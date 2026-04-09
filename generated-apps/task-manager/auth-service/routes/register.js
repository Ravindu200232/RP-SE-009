import express from "express";
import { registerUser } from "../controllers/authController.js";
import User from "../models/User.js";

const router = express.Router();

router.post("/", async (req, res) => {
  try {
    const existingUser = await User.findOne({ email: req.body.email });
    if (existingUser) return res.status(409).json({ message: "Email already registered" });

    const hashedPassword = bcrypt.hashSync(req.body.password, 10);
    const newUser = new User({
      email: req.body.email,
      password: hashedPassword
    });

    await newUser.save();
    return res.status(201).json(newUser);

  } catch (error) {
    console.error(error.message);
    return res.status(500).json({ error: "Internal server error" });
  }
});

export default router;