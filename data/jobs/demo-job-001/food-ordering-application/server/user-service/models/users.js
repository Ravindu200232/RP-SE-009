import mongoose from "mongoose";

const userSchema = new mongoose.Schema({

    firstName : {
        type : String,
        required : true,
    },
    lastName : {
        type : String,
        required : true,
    },
    email : {
        type : String,
        required : true,
        unique : true,
    },
    password : {
        type : String,
        required : true,
    },
    address :{
        type : String,
        required : true
    },
    role : {
        type : String,
        enum : ['customer','restaurant','delivery','admin'],
        default : 'customer',
        required : true,
    },
    phone : {
        type : String,
        required : true,
    },
    createdAt : {
        type : Date,
        default : Date.now,
    }
    ,
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
    emailVerified : {
        type : Boolean,
        required : true,
        default : false
    },
lat: {
    type: Number,
    required:false
},
lng: {
    type: Number,
    required:false
   
},

})

const User = mongoose.model('User',userSchema)

export default User;