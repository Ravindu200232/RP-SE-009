import React from "react";

export default function SkeletonBookingItem() {
  return (
    <div className="flex items-center p-4 bg-secondary rounded-lg shadow-md w-full animate-pulse">
      {/* Image Placeholder */}
      <div className="w-16 h-16 bg-gray-300 rounded-lg"></div>

      {/* Text Placeholder */}
      <div className="ml-4 flex-1">
        <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
        <div className="h-3 bg-gray-300 rounded w-1/2 mb-2"></div>
        <div className="h-3 bg-gray-300 rounded w-1/3"></div>
      </div>
    </div>
  );
}
