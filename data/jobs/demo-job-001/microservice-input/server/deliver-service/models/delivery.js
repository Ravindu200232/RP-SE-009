import mongoose from "mongoose";

const deliverySchema = mongoose.Schema({
  driverId: {
    type: String,
    required: true
  },
  driverName: {
    type : String,
    required : true
  },
  driverPhone : {
    type : String,
    required : true
  },
  customerEmail : {
    type : String,
    required : true
  },
  address : {
    type : String,
    required : true
  },
  phone : {
    type : String,
    required : true
  },
  orderId: {
    type: String,
    required: true
  },
  orderName : {
    type : String,
    required : true
  },
  itemImage : {
    type : String,
    required : true
  },
  price : {
    type : String,
    required : true
  },
  total : {
    type : String,
    required : true
  },
  qty :{
    type : String,
    required : true
  }
  ,
  status: {
    type: String,
    required: true,
    enum: ["picked up", "on the way", "delivered"],
    default: "picked up"
  },
estimatedTime: {
    type: Date, // Or use Number if it's a duration
    required: true
},
  
lat: {
        type: Number,
        required: true
      },
lng: {
        type: Number,
        required: true
      },
timestamp: {
        type: Date,
        required: true
      },
});

const Delivery = mongoose.model("delivery", deliverySchema);

export default Delivery;
