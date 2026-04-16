
import Restaurant from "../models/resturants.js";
import { checkAdmin, checkCustomer, checkHasAccount, checkRestaurant } from "./authController.js";
//create restaurant
export async function createRestaurant(req,res){

    try{
        if(checkHasAccount(req)){

            const data = req.body;
            data.ownerId = req.user.id;
            data.ownerName = `${req.user?.firstName || ''} ${req.user?.lastName || ''}`.trim();

            if(checkRestaurant(req)){

                const newRestaurant = new Restaurant(data);
                await newRestaurant.save();
                res.json({
                    message : "Restaurant added successfully"
                })
                return
                
            }else{
                res.status(401).json({
                    message : "Can't access this task"
                })
                return
            }
        }else{
            res.status(401).json({
                message : "Please login first"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }

}

//view restaurant
export async function getRestaurant(req,res){

    try{
        if(checkHasAccount(req)){

            if(checkAdmin(req)){

                const result = await Restaurant.find();
                res.json(result)
                return
            }

            if(checkRestaurant(req)){

                const result = await Restaurant.find({
                    ownerId : req.user.id
                })
                res.json(result)
                return
            }
            if(checkCustomer(req)){
                const result  = await Restaurant.find({
                    verified : true
                })
                res.json(result)
                return
            }else{
                res.json({
                    message : "can't access this task"
                })
                return
            }
            

        }else{
            const result  = await Restaurant.find({
                verified : true
            })
            res.json(result)
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal server error" || err
        })
    }
}

//update restaurant
export async function updateRestaurant(req,res) {

    try{

        const id = req.params.id;
        const data = req.body

        if(checkHasAccount(req)){
            if(checkAdmin(req)){

                const updateResult = await Restaurant.updateOne({
                    _id: id
                }, { verified: true });

                if (updateResult.modifiedCount === 0) {
                    res.status(404).json({
                        message: "No restaurant found to update"
                    });
                    return;
                }

                res.json({
                    message: "Update Successfully"
                });
                return;
            }
            
            if(checkRestaurant(req)){
                
                await Restaurant.updateOne({
                    _id : id,
                    ownerId : req.user.id
                },{
                    name : data.name,
                    address : data.address,
                    phone : data.phone,
                    image : data.image,
                    description : data.description,
    
                })
                res.json({
                    message : "Update Successfully"
                })
                return
            }else{
                res.status(401).json({
                    message : "can't do this task"
                })
                return
            }
        }else{
            res.status(401).json({
                message : "Please Login first"
            })
        }

        

    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
}

//delete restaurant
export async function deleteRestaurant(req,res) {

    try{
        const id = req.params.id
        console.log(req.user)
        if(checkHasAccount(req)){

            if(checkAdmin(req)){
                await Restaurant.deleteOne({
                    _id : id
                })
                res.json({
                    message : "Restaurant Delete Successfully"
                })
                return
            }

            if(checkRestaurant(req)){
                console.log(req.user,id)
                await Restaurant.deleteOne({
                    ownerId : req.user.id,
                    _id : id
                })
                res.json({
                    message : "Restaurant Deleted Successfully"
                })
                return
            }
            res.json({
                message : "can't access this task"
            })
            
        }else{
            res.status(401).json({
                message : "Please login first"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}

export async function isOpen(req,res) {
    
    try{

        const id = req.params.id
        if(checkHasAccount(req)){
            
            if(checkAdmin(req)){

                await Restaurant.updateOne({
                    _id : id
                },{
                    isOpen : true
                })
                res.json({
                    message : "Shop informing Shop is Open now"
                })
                return
            }

            if(checkRestaurant(req)){

                await Restaurant.updateOne({
                    _id : id,
                    ownerId : req.user.id
                },{
                    isOpen : true
                })
                res.json({
                    message : "Shop informing Shop is Open now"
                })
                return
            }

            else{
                res.status(401).json({
                    message : "can't access this task"
                })
                return
            }
            
        }else{
            res.status(401).json({
                message : "Please login"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error " || err
        })
    }
}


export async function closeShop(req, res) {
    try {
      const id = req.params.id;
  
      if (checkHasAccount(req)) {
        if (checkAdmin(req)) {
          await Restaurant.updateOne({ _id: id }, { isOpen: false });
          return res.json({ message: "Shop is now closed." });
        }
  
        if (checkRestaurant(req)) {
          await Restaurant.updateOne({ _id: id, ownerId: req.user.id }, { isOpen: false });
          return res.json({ message: "Shop is now closed." });
        }
  
        return res.status(401).json({ message: "Unauthorized access." });
      } else {
        return res.status(401).json({ message: "Please login" });
      }
    } catch (err) {
      res.status(500).json({ error: "Internal Server Error" });
    }
  }
  

export async function verification(req,res) {
    
    try{
        const id = req.params.id;
       

        if(checkHasAccount(req)){

            if(checkAdmin(req)){
                await Restaurant.updateOne({
                    _id : id
                },{
                    verified : true,
                })
                res.json({
                    message : "Restaurant verification Successfully"
                })
                return
            }else{
                res.status(401).json({
                    message : "can't access this task"
                })
                return
            }
        }else{
            res.status(401).json({
                message : "Please login"
            })
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error " || err
        })
    }
}





export async function getOne(req,res) {

    try{

        const id = req.params.id

        const result = await Restaurant.findOne({
            _id : id
        })
        res.json(result)
    }
    catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}




