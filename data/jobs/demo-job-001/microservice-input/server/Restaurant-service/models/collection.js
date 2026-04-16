import mongoose from "mongoose";

const collectionSchema = new mongoose.Schema({

    restaurantId: {
        type: String,
        required: true
    },
    ownerId: {
        type: String,
        required: true
    },
    itemId: {
        type: String,
        required: true,
    },
    name: {
        type: String,
        required: true,
    },
    description: {
        type: String,
        required: true
    },
    price: {
        type: String,
        required: true
    },
    available: {
        type: Boolean,
        required: true,
        default: false
    },
    category: {
        type: String,
        required: true,
        enum: ["fastfood", "familyMeals", "dessert"]
    },
    isApprove: {
        type: Boolean,
        required: true,
        default: false,
    },
    images: {
        type: [String],
        required: true,
        default: ['https://www.pngall.com/wp-content/uploads/5/Collection-PNG-Image.png']
    },
});

const Collection = mongoose.model("collection",collectionSchema)

export default Collection