import { useState, useRef } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";
import mediaUpload from "../../utils/mediaUpload";

export default function DriverRegister() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [image, setImage] = useState("https://img.freepik.com/free-vector/blue-circle-with-white-user_78370-4707.jpg");
  const [vehicleType, setVehicleType] = useState("");
  const [drNic, setDrNic] = useState("");
  const role = "delivery"; // Hidden and fixed
  const fileInputRef = useRef();
  const navigate = useNavigate();

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const uploadedUrl = await mediaUpload(file);
      setImage(uploadedUrl);
      toast.success("Image uploaded successfully!");
    } catch (err) {
      console.error("Image upload failed", err);
      toast.error("Image upload failed.");
    }
  };

  const handleOnSubmit = async (e) => {
    e.preventDefault();

    if(image == ""){
      toast.success("Please upload profile picture")
      return
    }

    try {
      await axios.post(`${import.meta.env.VITE_DELIVER_SERVICE_URL}/api/v1/driver`, {
        email,
        password,
        firstName,
        lastName,
        address,
        phone,
        image,
        vehicleType,
        drNic,
        role, // Fixed as "delivery"
      });
      toast.success("Registration Successfully")
      
      
      navigate("/login");
    } catch (err) {
      console.error(err);
      toast.error(err?.response?.data?.error || "Email Already Added");
    }
  };

  return (
    <form onSubmit={handleOnSubmit}>
      <div className="w-full h-screen flex justify-center items-center bg-picture">
        <div className="w-[400px] h-[700px] backdrop-blur-xl rounded-2xl flex flex-col justify-center items-center relative">
          <span className="text-white text-3xl mt-24 mb-4">Register as Driver</span>

          {/* Profile Image Upload */}
          <div
            className="cursor-pointer mb-4"
            onClick={() => fileInputRef.current.click()}
          >
            <img
              src={image || "https://via.placeholder.com/100?text=Upload"}
              alt="Profile"
              className="w-24 h-24 object-cover rounded-full border-2 border-white"
            />
            <label className="text-white text-sm mt-2 cursor-pointer">
              Click to upload image
            </label>
          </div>
          <input
          
            type="file"
            accept="image/*"
            ref={fileInputRef}
            onChange={handleImageUpload}
            className="hidden"
          />

          {/* /* Form Fields */} 
                <input
                required
                type="text"
                placeholder="First Name"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setFirstName(e.target.value.replace(/[^a-zA-Z\s]/g, ""))}
                value={firstName}
                />
                <input
                required
                type="text"
                placeholder="Last Name"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setLastName(e.target.value.replace(/[^a-zA-Z\s]/g, ""))}
                value={lastName}
                />
                <input
                required
                type="email"
                placeholder="Email"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setEmail(e.target.value)}
                value={email}
                />
                <input
                required
                type="password"
                placeholder="Password"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setPassword(e.target.value)}
                value={password}
                pattern="^(?=.*[A-Z])(?=.*[\W_]).{8,}$"
                title="Password must be at least 8 characters long and include at least one uppercase letter and one symbol."
                />
                <input
                required
                type="text"
                placeholder="Address"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setAddress(e.target.value)}
                value={address}
                />
                <input
                required
                type="number"
                placeholder="Phone"
                className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
                onChange={(e) => setPhone(e.target.value)}
                value={phone}
                />

                {/* Vehicle Type Dropdown */}
          <select
          required
            value={vehicleType}
            onChange={(e) => setVehicleType(e.target.value)}
            className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
          >
            <option className="text-black" value="" disabled>Select Vehicle Type</option>
            <option className="text-black" value="Car">Car</option>
            <option className="text-black" value="Bike">Bike</option>
            <option className="text-black" value="Van">Van</option>
            <option className="text-black" lassName="text-black" value="Truck">Truck</option>
            {/* Add other vehicle types as needed */}
          </select>

          <input
          required
            type="text"
            placeholder="Driver NIC"
            className="placeholder:text-white w-[300px] h-[40px] bg-transparent border-b-2 border-white text-xl text-white outline-none mb-3"
            onChange={(e) => setDrNic(e.target.value)}
            value={drNic}
          />

          <button className="mt-4 w-[300px] h-[50px] bg-[#010750] text-xl text-white rounded-lg">
            Register
          </button>

          <span className="text-white text-sm mt-4 mb-2">
            Already have an account?{" "}
            <span
              className="text-blue-400 cursor-pointer"
              onClick={() => navigate("/login")}
            >
              Login
            </span>
          </span>
        </div>
      </div>
    </form>
  );
}
