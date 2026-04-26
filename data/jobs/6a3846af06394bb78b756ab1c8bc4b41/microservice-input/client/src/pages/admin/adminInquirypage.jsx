import { useEffect, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";

export function AdminInquiryPage() {
  const [inquiries, setInquiries] = useState([]);
  const [responseMap, setResponseMap] = useState({});

  const fetchInquiries = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setInquiries(res.data || []);
    } catch (error) {
      console.error("Failed to fetch inquiries", error);
    }
  };

  const handleResponseChange = (id, value) => {
    setResponseMap((prev) => ({ ...prev, [id]: value }));
  };

  const handleUpdateResponse = async (id) => {
    const token = localStorage.getItem("token");
    const response = responseMap[id];

    if (!response || !response.trim()) {
      Swal.fire("Warning", "Response cannot be empty.", "warning");
      return;
    }

    try {
      await axios.put(
        `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry/${id}`,
        { response },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      Swal.fire("Success", "Response updated successfully.", "success");
      fetchInquiries();
    } catch (error) {
      console.error("Failed to update response", error);
      Swal.fire("Error", "Failed to update response.", "error");
    }
  };

  const handleDeleteInquiry = async (id) => {
    const confirmed = await Swal.fire({
      title: "Are you sure?",
      text: "This inquiry will be permanently deleted.",
      icon: "warning",
      showCancelButton: true,
      confirmButtonColor: "#d33",
      confirmButtonText: "Yes, delete it!",
    });

    if (confirmed.isConfirmed) {
      try {
        const token = localStorage.getItem("token");
        await axios.delete(
          `${import.meta.env.VITE_USER_SERVICE_URL}/api/inquiry/${id}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        Swal.fire("Deleted!", "Inquiry has been deleted.", "success");
        fetchInquiries();
      } catch (error) {
        console.error("Failed to delete inquiry", error);
        Swal.fire("Error", "Failed to delete inquiry.", "error");
      }
    }
  };

  useEffect(() => {
    fetchInquiries();
  }, []);

  return (
    <div className="p-4 sm:p-6">
      <h1 className="text-xl sm:text-2xl font-bold mb-4">Admin - Inquiries</h1>

      {inquiries.length === 0 ? (
        <p className="text-center text-gray-500 mt-10">No inquiries found.</p>
      ) : (
        <div className="space-y-6">
          {inquiries.map((inq) => (
            <div
              key={inq._id}
              className="border rounded-lg shadow-md p-4 bg-white space-y-4"
            >
              <div className="text-sm text-gray-500">ID: {inq.id}</div>
              <div className="text-sm">Phone: {inq.phone || "Unknown"}</div>
              <div className="text-sm">Email: {inq.email}</div>
              <div className="text-sm font-medium">Message:</div>
              <p className="bg-gray-100 p-2 rounded text-sm">{inq.message}</p>

              <div className="mt-2">
                <label className="block text-sm font-medium mb-1">
                  Response:
                </label>
                <textarea
                  rows={3}
                  className="w-full p-2 border rounded text-sm"
                  value={responseMap[inq._id] ?? inq.response ?? ""}
                  onChange={(e) =>
                    handleResponseChange(inq._id, e.target.value)
                  }
                />
              </div>

              <div className="flex flex-col sm:flex-row sm:space-x-2 mt-2 space-y-2 sm:space-y-0">
                <button
                  onClick={() => handleUpdateResponse(inq._id)}
                  className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
                >
                  Send Response
                </button>
                <button
                  onClick={() => handleDeleteInquiry(inq._id)}
                  className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
