import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom"; // <-- Step 1

export default function VerifyEmail() {
  const token = localStorage.getItem("token");
  const [otp, setOtp] = useState("");
  const [status, setStatus] = useState("Click the button to send OTP.");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(null);
  const [cooldown, setCooldown] = useState(0);
  const [verifying, setVerifying] = useState(false);

  const navigate = useNavigate(); // <-- Step 2

  const sendOTP = async () => {
    if (!token) {
      setStatus("Token not found. Please login again.");
      setSuccess(false);
      return;
    }

    setLoading(true);
    setStatus("Sending verification email...");
    try {
      const response = await fetch(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/sendOTP`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        console.log("OTP sent:", data);
        setStatus("Verification email with OTP sent successfully!");
        setSuccess(true);
        setCooldown(30);
      } else {
        const errorData = await response.json();
        setStatus(errorData.message || "Failed to send verification email.");
        setSuccess(false);
      }
    } catch (error) {
      console.error(error);
      setStatus("An error occurred while sending the OTP.");
      setSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  const verifyOTP = async () => {
    if (!otp || !token) {
      setStatus("Please enter the OTP.");
      setSuccess(false);
      return;
    }

    setVerifying(true);
    setStatus("Verifying OTP...");

    try {
      const response = await fetch(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/verifyOTP`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ otp }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        setStatus("OTP verified successfully! ✅");
        setSuccess(true);
        console.log("OTP Verified:", data);
        setTimeout(() => {
          navigate("/login"); // <-- Step 3: Redirect after success
        }, 2000); // optional 2s delay for user to see the success message
      } else {
        const errorData = await response.json();
        setStatus(errorData.message || "OTP verification failed.");
        setSuccess(false);
      }
    } catch (error) {
      console.error("Error verifying OTP:", error);
      setStatus("An error occurred while verifying OTP.");
      setSuccess(false);
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => {
    if (cooldown === 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-blue-200 via-purple-200 to-pink-200">
      <div className="bg-white p-8 rounded-2xl shadow-2xl w-[90%] max-w-md text-center animate-fade-in">
        <h2 className="text-3xl font-bold mb-4 text-[#1A237E]">
          Verify Your Email
        </h2>

        {loading || verifying ? (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 border-4 border-blue-600 border-dashed rounded-full animate-spin mb-4"></div>
            <p className="text-lg font-medium text-blue-700">{status}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            {success !== null && (
              <img
                src={
                  success
                    ? "https://png.pngtree.com/png-vector/20190724/ourmid/pngtree-true-sign-png-png-image_1589429.jpg"
                    : "https://w7.pngwing.com/pngs/595/505/png-transparent-computer-icons-error-closeup-miscellaneous-text-logo.png"
                }
                alt="status"
                className="w-16 h-16 rounded-full"
              />
            )}
            <p
              className={`text-lg font-semibold ${
                success === null
                  ? "text-gray-700"
                  : success
                  ? "text-green-600"
                  : "text-red-600"
              }`}
            >
              {status}
            </p>

            <input
              type="number"
              placeholder="Enter OTP"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-md w-full text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            <button
              onClick={verifyOTP}
              className="w-full py-2 bg-green-600 text-white rounded-lg text-lg hover:bg-green-700 transition"
            >
              Verify OTP
            </button>

            <button
              onClick={sendOTP}
              disabled={cooldown > 0}
              className={`w-full py-2 text-lg font-medium rounded-lg transition ${
                cooldown > 0
                  ? "bg-gray-400 cursor-not-allowed text-white"
                  : "bg-[#1A237E] text-white hover:bg-[#0D1B56]"
              }`}
            >
              {cooldown > 0 ? `Resend OTP in ${cooldown}s` : "Send OTP"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
