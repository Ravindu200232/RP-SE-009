import Review from "../models/review.js";
import { checkAdmin, checkRestaurant } from "./authController.js";



export async function  addReview(req,res){
   
    const data = req.body
    
   

    if(req.user == null){
        res.json({
            message : "Please login and try again"
        })
        return
    }

    data.name = req.user.firstName + " " + req.user.lastName;
    data.profilePicture = req.user.image;
    data.email = req.user.email
    console.log(data)

    const newReview = new Review(data)
    

    try{
        await newReview.save();
        res.json({
            message : "Review added successfully"
        })

    }catch(err){
        res.status(401).json({
            err : "Review added failed!"
        })

    }
    
}

export async function getReview(req,res){

    const user = req.user;
    

   if(user == null || user.role == !"admin"){

    try{
        const review = await Review.find({isApproved : true});
        res.json(review)
    }catch(err){
        (err)=>{
            res.status(500).json({
                err : err
            })
        }

    }


   

   
   }

   if(checkRestaurant(req)){
    try{
        const review = await Review.find({ownerId : req.user.id});
        res.json(review)
    }catch(err){
        (err)=>{
            res.status(500).json({
                err : err
            })
        }

    }
}

   if(checkAdmin(req)){

   
    try{
        const review = await Review.find();
        res.json(review);
    }catch(err){
        res.json(err);
    }
    
    
   }

    

   

}

export async function deleteReview(req,res){

    const id = req.params.id

    if(req.user == null){
        res.status(401).json({
            message : "Please login your Account"
        })
        return
    }

    try{
        if(req.user.role == "admin"){
            await Review.deleteOne({
                _id : id
            })
            res.json({
                message : "delete Successfully"
            })
        }
        if(req.user.role == "customer" && email == req.user.email){
            await Review.deleteOne({
                _id : id
            })
            res.json({
                message : "delete Successfully"
            })
        }
        

    }catch(err){
        res.status(500).json({
            err : "delete unsuccessfully"
        })
    }

}

export async function approveReview(req,res){

    const id = req.params.id;
    

    
    try{
        if(req.user == null){
            res.status(401).json({
                message : "please login"
            })
            return
        }
    
    
        if(checkAdmin(req)){
            await Review.updateOne({
                _id : id
            },
            {
                isApproved : true
            })
            res.json({
                message : "isApproved successfully"
            })
        }else{
            res.json({
              message : "You are not admin"
            })
        }

    }catch(err){
        res.status(500).json({
            err : "isApproved unsuccessfully"
        })
    }
}

export async function disApproveReview(req,res){

    try{
        const key = req.params.key;
        
            
                const result = await Review.find({
                    productId : key,
                    isApproved : true,
                })
                res.json(result);
            
        

    }catch(err){
        res.status(500).json({
            err : "isApproved unsuccessfully"
        })
    }
}