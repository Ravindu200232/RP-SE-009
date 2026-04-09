import mongoose from "mongoose";
import bcrypt from "bcryptjs";

const userSchema = new mongoose.Schema({
  email: { type: String, required: true },
  password: { type: String, required: true }
}, { timestamps: true });

userSchema.pre("save", function(next) {
  if (!this.isModified("password")) return next();
  
  this.password = bcrypt.hashSync(this.password, 10);
  next();
});

export default mongoose.model("User", userSchema);
