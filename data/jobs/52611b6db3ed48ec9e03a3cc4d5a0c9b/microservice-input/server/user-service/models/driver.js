import mongoose from "mongoose";

const driverSchema = new mongoose.Schema({

    
    firstName : {
        type : String,
        required : true,
    },
    lastName : {
        type : String,
        required : true,
    }
    ,
    email : {
        type : String,
        required : true
    },
    phone : {
        type : String,
        required : true,
    },
    role : {
        type : String,
        required : true,
        default : "delivery",
    },
    password : {
        type : String,
        required : true
    },
    vehicleType : {
        type : String,
        required : true,
    },
    drNic : {
        type : String,
        required : true
    },
    isAvailable : {
        type : Boolean,
        required : true,
        default : false,
    },
    address : {
        type : String,
        required : true
    },
    isVerified : {
        type : Boolean,
        default : false,
        required : true,
    },
    isBlock : {
        type : Boolean,
        default : false,
        required : true,
    },
    image : {
        type : String,
        required : true,
        default : "https://img.freepik.com/free-vector/blue-circle-with-white-user_78370-4707.jpg"
    },
})

const Driver = mongoose.model("driver",driverSchema);

export default Driver