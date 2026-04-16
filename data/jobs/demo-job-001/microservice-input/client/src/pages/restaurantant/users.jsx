import axios from "axios";
import { useEffect, useState } from "react";

export default function User() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  // Fetch users
  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(
          `${import.meta.env.VITE_BACKEND_URL}/api/users`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setUsers(response.data);
      } catch (error) {
        console.error("Error fetching users:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  // Handle Block/Unblock User
  const handleBlockUser = async (email, isBlocked) => {
    try {
      setLoading(true);
      const token = localStorage.getItem("token");
      await axios.put(
        `${import.meta.env.VITE_BACKEND_URL}/api/users/block/${email}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Update state
      setUsers((prevUsers) =>
        prevUsers.map((user) =>
          user.email === email ? { ...user, isBlocked: !isBlocked } : user
        )
      );
    } catch (error) {
      console.log("Error updating user status:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full min-h-screen bg-gray-100 flex flex-col items-center py-10">
      <h1 className="text-3xl font-bold text-gray-700 mb-6">User Management</h1>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="w-16 h-16 border-4 border-blue-500 border-dashed rounded-full animate-spin"></div>
        </div>
      ) : (
        <>
          {/* Table for larger screens */}
          <div className="hidden sm:block w-full max-w-6xl bg-white shadow-lg rounded-lg overflow-x-auto overflow-y-auto">
            <table className="w-full border-collapse">
              <thead className="bg-primary text-white">
                <tr>
                  <th className="py-3 px-4 text-center">Profile</th>
                  <th className="py-3 px-4 text-left">Email</th>
                  <th className="py-3 px-4 text-left">Role</th>
                  <th className="py-3 px-4 text-left">First Name</th>
                  <th className="py-3 px-4 text-left">Last Name</th>
                  <th className="py-3 px-4 text-left">Address</th>
                  <th className="py-3 px-4 text-left">Phone</th>
                  <th className="py-3 px-4 text-center">Status</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user._id} className="hover:bg-gray-100">
                    <td className="py-3 px-4 flex justify-center">
                      <img
                        src={user.image || "/default-profile.png"}
                        className="w-14 h-14 rounded-full object-cover border-2 border-gray-300"
                        alt="Profile"
                      />
                    </td>
                    <td className="py-3 px-4">{user.email}</td>
                    <td className="py-3 px-4 capitalize">{user.role}</td>
                    <td className="py-3 px-4">{user.firstName}</td>
                    <td className="py-3 px-4">{user.lastName}</td>
                    <td className="py-3 px-4">{user.address}</td>
                    <td className="py-3 px-4">{user.phone}</td>
                    <td className="py-3 px-4 flex justify-center">
                      <button
                        className={`px-3 py-1 text-sm font-semibold rounded-full cursor-pointer ${
                          user.isBlocked
                            ? "bg-red-500 hover:bg-red-700 text-white"
                            : "bg-green-500 hover:bg-green-700 text-white"
                        }`}
                        onClick={() =>
                          handleBlockUser(user.email, user.isBlocked)
                        }
                      >
                        {user.isBlocked ? "BLOCKED" : "ACTIVE"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile view for users */}
          <div className="block sm:hidden w-full max-w-6xl bg-white shadow-lg rounded-lg overflow-x-auto overflow-y-auto">
            {users.map((user) => (
              <div
                key={user._id}
                className="p-4 mb-4 border-b hover:bg-gray-50"
              >
                <div className="flex items-center mb-4">
                  <img
                    src={user.image || "/default-profile.png"}
                    alt="Profile"
                    className="w-16 h-16 rounded-full object-cover border-2 border-gray-300"
                  />
                  <div className="ml-4">
                    <p className="font-medium text-lg">
                      {user.firstName} {user.lastName}
                    </p>
                    <p className="text-gray-600">{user.email}</p>
                    <p className="text-sm text-gray-500">{user.role}</p>
                  </div>
                </div>

                <div className="mb-2">
                  <p className="text-sm text-gray-700">
                    <strong>Address:</strong> {user.address}
                  </p>
                  <p className="text-sm text-gray-700">
                    <strong>Phone:</strong> {user.phone}
                  </p>
                </div>

                <div className="flex justify-between items-center">
                  <button
                    onClick={() => handleBlockUser(user.email, user.isBlocked)}
                    className={`w-full px-4 py-2 rounded-full text-white ${
                      user.isBlocked
                        ? "bg-red-500 hover:bg-red-700"
                        : "bg-green-500 hover:bg-green-700"
                    }`}
                  >
                    {user.isBlocked ? "BLOCKED" : "ACTIVE"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
