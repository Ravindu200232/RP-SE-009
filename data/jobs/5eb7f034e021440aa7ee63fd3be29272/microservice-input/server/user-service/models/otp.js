import mongoose from "mongoose";

const OTPSchema = new mongoose.Schema({
    email: {
        type: String,
        required: true,
    },
    otp: {
        type: String,
        required: true,
    },
    createdAt: {
        type: Date,
        required: true,
        default: Date.now,
        expires: 300, // OTP expires in 5 minutes
    },
});
const OTP = mongoose.model("OTP", OTPSchema);

export default OTP;