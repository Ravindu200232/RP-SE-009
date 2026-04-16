import { useState } from "react";

export default function ImageSlider(props) {
  const images = props.images;
  const [selectedImage, setSelectedImage] = useState(images[0]);

  return (
    <div className="w-full h-full flex flex-col items-center">
      <img
        src={selectedImage}
        alt="product"
        className="w-[90%] h-[450px] object-cover rounded-lg"
      ></img>
      <div className="w-full h-[150px] mt-[20px] flex justify-center">
        {images.map((image, index) => {
          return (
            <img
              key={index}
              src={image}
              alt={`product-${index}`}
              className={`w-[90px] h-[90px] object-cover cursor-pointer ml-[2px] ${
                image == selectedImage ? "border border-accent" : ""
              }`}
              onClick={() => {
                setSelectedImage(image);
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
