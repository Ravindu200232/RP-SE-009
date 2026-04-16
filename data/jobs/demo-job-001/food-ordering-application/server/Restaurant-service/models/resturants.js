import mongoose from "mongoose";

const restaurantSchema = new mongoose.Schema({
    ownerId: {
        type: String,
        required: true,
    },
    ownerName: {
        type: String,
        required: true,
    },
    name: {
        type: String,
        required: true,
        unique : true,
    },
    address: {
        type: String,
        required: true,
    },
    phone: {
        type: String,
        required: true,
    },
    images: {
        type: [String],
        required: true,
        default: ['https://www.pngall.com/wp-content/uploads/5/Restaurant-PNG-Image.png']
    },
    description: {
        type: String,
        required: true,
    },
    isOpen: {
        type: Boolean,
        default: false,
    },
    verified: {
        type: Boolean,
        default: false,
    },
});

const Restaurant = mongoose.model("Restaurant",restaurantSchema);

export default Restaurant