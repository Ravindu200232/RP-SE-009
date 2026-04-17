import { useEffect, useRef, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";

const GOOGLE_MAPS_API_KEY = "AIzaSyCMMHWV8VSCEoqws7_Rh2Crea_rSPvv1t0"; // Replace with your actual key

export function Location() {
  const mapRef = useRef(null);
  const [formData, setFormData] = useState({
    address: "",
    lat: "",
    lng: "",
  });

  const loadGoogleMapsScript = () => {
    const existingScript = document.getElementById("googleMapsScript");
    if (existingScript) return;

    const script = document.createElement("script");
    script.id = "googleMapsScript";
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}`;
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
  };

  useEffect(() => {
    loadGoogleMapsScript();
  }, []);

  const initMap = (lat, lng) => {
    if (!window.google || !mapRef.current) return;
    const map = new window.google.maps.Map(mapRef.current, {
      center: { lat, lng },
      zoom: 15,
    });

    new window.google.maps.Marker({
      position: { lat, lng },
      map,
      title: "You are here",
    });
  };

  const getLocation = () => {
    if (!navigator.geolocation) {
      Swal.fire("Error", "Geolocation is not supported by your browser.", "error");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;

        try {
          const res = await axios.get(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
          );
          const location = res.data?.display_name || "";
          setFormData({
            address: location,
            lat: latitude.toString(),
            lng: longitude.toString(),
          });

          Swal.fire("Success", "Location fetched successfully!", "success");
          initMap(latitude, longitude); // Show the map
        } catch (err) {
          console.error("Reverse geocoding failed", err);
          Swal.fire("Error", "Failed to fetch location details.", "error");
        }
      },
      (error) => {
        console.error("Geolocation error:", error);
        Swal.fire("Error", "Failed to access your location.", "error");
      }
    );
  };

  const handleUpdateLocation = async () => {
    const user = JSON.parse(localStorage.getItem("user"));
    const token = localStorage.getItem("token");

    if (!user || !token) {
      Swal.fire("Error", "User not logged in", "error");
      return;
    }

    try {
      const updateData = {
        address: formData.address,
        lat: formData.lat,
        lng: formData.lng,
      };

      await axios.put(
        `${import.meta.env.VITE_BACKEND_URL}/api/users/update/${user.id}`,
        updateData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const updatedUser = { ...user, ...updateData };
      localStorage.setItem("user", JSON.stringify(updatedUser));

      Swal.fire("Success", "Location data updated successfully!", "success");
    } catch (error) {
      console.error("Update failed", error);
      Swal.fire("Error", "Failed to update user location.", "error");
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="space-x-4 mb-4">
        <button
          onClick={getLocation}
          className="bg-blue-600 text-white px-4 py-2 rounded shadow-md hover:bg-blue-700"
        >
          Use Current Location
        </button>

        <button
          onClick={handleUpdateLocation}
          className="bg-green-600 text-white px-4 py-2 rounded shadow-md hover:bg-green-700"
        >
          Update User Location
        </button>
      </div>

      <div
        ref={mapRef}
        style={{
          width: "100%",
          height: "400px",
          marginTop: "20px",
          borderRadius: "10px",
        }}
      ></div>
    </div>
  );
}
