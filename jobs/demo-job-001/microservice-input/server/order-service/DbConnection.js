import mongoose from 'mongoose';

export function connectToDatabase() {

    const MONGOURL =  process.env.MONGO_URL;

    mongoose.connect(MONGOURL);

    const connection = mongoose.connection;
    connection.once('open',()=>{
        console.log("MongoDB database connection established successfully");
    })
}