import { useEffect, useState } from "react";
import axios from "axios";
import Swal from "sweetalert2";

export function RestaurantReview() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchReviews = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(
        `${import.meta.env.VITE_RESTAURANT_SERVICE_URL}/api/v1/reviews`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      setReviews(response.data);
    } catch (error) {
      console.error("Error fetching reviews:", error);
    } finally {
      setLoading(false);
    }
  };

  

  

  useEffect(() => {
    fetchReviews();
  }, []);

  if (loading) return <div>Loading reviews...</div>;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-4">Review Management</h2>

      {/* Table for larger screens */}
      <div className="hidden sm:block overflow-x-auto">
        <table className="min-w-full bg-white border rounded-md shadow-md">
          <thead>
            <tr className="bg-gray-100 text-left text-sm font-semibold text-gray-700">
              <th className="py-3 px-4 border-b">User</th>
              <th className="py-3 px-4 border-b">Email</th>
              <th className="py-3 px-4 border-b">Rating</th>
              <th className="py-3 px-4 border-b">Comment</th>

              <th className="py-3 px-4 border-b">Status</th>
              <th className="py-3 px-4 border-b">ITem</th>
              <th className="py-3 px-4 border-b">RestaurantName</th>
              
            </tr>
          </thead>
          <tbody>
            {reviews.map((review) => (
              <tr
                key={review._id}
                className="border-b hover:bg-gray-50 text-sm"
              >
                <td className="py-3 px-4 flex items-center gap-2">
                  <img
                    src={review.profilePicture}
                    alt="profile"
                    className="w-8 h-8 rounded-full"
                  />
                  {review.name}
                </td>
                <td className="py-3 px-4">{review.email}</td>
                <td className="py-3 px-4">{review.rating} / 5</td>
                <td className="py-3 px-4">{review.comment}</td>
                <td className="py-3 px-4">
                  {review.isApproved ? (
                    <span className="text-green-600 font-medium">Approved</span>
                  ) : (
                    <span className="text-yellow-600 font-medium">Pending</span>
                  )}
                </td>
                <td className="py-3 px-4">{review.itemName}</td>
                <td className="py-3 px-4">{review.restaurantName}</td>
               
              </tr>
            ))}

            {reviews.length === 0 && (
              <tr>
                <td colSpan="6" className="text-center py-6 text-gray-500">
                  No reviews found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile view for reviews */}
      <div className="block sm:hidden">
        {reviews.length === 0 ? (
          <p className="text-center text-gray-500 mt-10">No reviews found.</p>
        ) : (
          reviews.map((review) => (
            <div
              key={review._id}
              className="border rounded-lg shadow-md p-4 mb-4 bg-white"
            >
              <div className="flex items-center mb-2">
                <img
                  src={review.profilePicture}
                  alt="profile"
                  className="w-10 h-10 rounded-full mr-3"
                />
                <div>
                  <p className="font-medium">{review.name}</p>
                  <p className="text-sm text-gray-500">{review.email}</p>
                </div>
              </div>
              <p className="text-sm">{review.comment}</p>
              <div className="mt-2 text-sm font-semibold">
                Rating: {review.rating} / 5
              </div>
              <div className="mt-2">
                <span
                  className={`${
                    review.isApproved ? "text-green-600" : "text-yellow-600"
                  }`}
                >
                  {review.isApproved ? "Approved" : "Pending"}
                </span>
              </div>

             
            </div>
          ))
        )}
      </div>
    </div>
  );
}
