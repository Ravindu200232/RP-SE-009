import mongoose from "mongoose";

const reviewShema = new mongoose.Schema({

    productId : {
        type : String,
        required : true
    },
    email : {
        type : String,
        required : true,
    },
    itemName : {
        type : String,
        required : true
    },
    name : {
        type : String,
        required : true
    },
    rating : {
        type : Number,
        required : true
    },
    comment : {
        type : String,
        required : true
    },
    ownerId : {
        type : String,
        required : true
    },
    restaurantName : {
        type : String,
        required : true
    },
    data : {
        type : Date,
        required : true,
        default : Date.now()

    },
    profilePicture : {
        type : String,
        required : true,
        default : "https://img.freepik.com/free-vector/blue-circle-with-white-user_78370-4707.jpg"
    },

    isApproved : {
    type : Boolean,
    required : true,
    default : false
}

})

const Review = mongoose.model("review",reviewShema);
export default Review;