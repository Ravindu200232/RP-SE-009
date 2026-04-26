import bcrypt from "bcrypt"
import Driver from "../models/driver.js";
import jwt from "jsonwebtoken"
import { checkAdmin, checkDelivery, checkHasAccount, checkRestaurant } from "./authController.js";



export async function createDriver(req,res){

    try{
        const data = req.body;
        data.password = await bcrypt.hashSync(data.password,10);
        const email = data.email;

        const checkEmail = await Driver.findOne({
            email : email
        })

        if(checkEmail){
            res.json({
                message : "Email is Already use"
            })
            return
        }else{
            const newUser = new Driver(data);
            await newUser.save();
            res.json({
                message : "Driver Added!"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            err : "Driver registration failed"
        })
    }





}


export async function driverLogin(req,res) {

    try{

        const data = req.body;
        const email = data.email;

        const checkUser = await Driver.findOne({
            email : email
        })

        if(checkUser){

            const checkPassword = bcrypt.compareSync(
                data.password,checkUser.password
            );

            if(checkPassword){
                const token = jwt.sign(
                    {
                        id : checkUser._id,
                        firstName : checkUser.firstName,
                        lastName : checkUser.lastName,
                        email : checkUser.email,
                        password : checkUser.password,
                        role : checkUser.role,
                        phone : checkUser.phone,
                        image : checkUser.image

                    },
                    process.env.SEKRET_KEY
                );
                res.json({
                    message : "Login successfully",
                    token : token,
                    user : checkUser
                })
                return
            }else{
                res.json({
                    message : "Password incorrect ,please try again!"
                })
                return
            }

        }else{
            res.status(404).json({
                message : "driver not found please try again!"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            err : "driver Login unsuccessfully!"
        })
    }

}

export async function getDriver(req,res) {
    
    try{

        if(checkHasAccount(req)){

            if(checkAdmin(req)){
                const result = await Driver.find();
                res.json(result);
                return
            }
            if(checkRestaurant(req)){
                const result = await Driver.find({
                    isAvailable : true
                })
                res.json(result)
                return
            }
            if(checkDelivery(req)){
                const result = await Driver.findOne({
                    _id : req.user.id
                })
                res.json(result)
                return
            }
            res.status(401).json({
                message : "can't access this task"
            })
            return

        }else{
            res.status(401).json({
                message : "Please login"
            })
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Error " || err
        })
    }
    
}

export async function updateDriver(req,res) {

    try{

        const id = req.params.id
        const data = req.body

        if(checkHasAccount(req)){

            if(checkAdmin(req)){
                await Driver.updateOne({
                    _id : id
                }, data)
                res.json("Driver update successfully")
                return
                
            }
            if(checkDelivery(req)){
                await Driver.updateOne({
                    _id : req.user.id
                },data)
                res.json({
                    message : "Driver update successfully"
                })
                return
            }

            res.status(401).json({
                message : "can't access this task"
            })
            return
        }else{
            res.status(401).json({
                message : "please login"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}

export async function deleteDriver(req,res) {

    try{
        const id = req.params.id;

        if(checkHasAccount(req)){

            if(checkAdmin){
                await Driver.deleteOne({
                    _id : id
                })
                res.json({
                    message : "Driver deleted successfully"
                })
                return
            }
            if(checkDelivery(req)){
                await Driver.deleteOne({
                    _id : req.user.id
                })
                res.json({
                    message : "Driver deleted successfully"
                })
                return
            }

            res.status(401).json({
                message : "can't access this task"
            })
            return
            
        }else{
            res.status(401).json({
                message : "Please login"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}






