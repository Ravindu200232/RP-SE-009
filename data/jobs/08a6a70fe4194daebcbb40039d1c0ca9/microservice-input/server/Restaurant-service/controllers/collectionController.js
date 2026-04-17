
import Collection from "../models/collection.js"
import Restaurant from "../models/resturants.js";
import { checkAdmin, checkHasAccount, checkRestaurant } from "./authController.js"
// create collection
export async function createCollection(req,res) {

    try{
        const data = req.body
        data.ownerId= req.user.id
        data.itemId = "I" + Math.floor(Math.random() * 10000).toString().padStart(4, '0')

        if(checkHasAccount(req)){

            if(checkAdmin(req) || checkRestaurant(req)){

                const newCollection = new Collection(data);
                await newCollection.save();
                res.json({
                    message : "Collection create successfully"
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
//view collection
export async function getRestaurantCollection(req,res) {
    
    try{

        const restaurantID = req.params.id;

        

           
                
                 const result = await Collection.find({
                     restaurantId:  restaurantID
                 })
                 res.json(result)
                 return
                
        
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
}

export async function getAll(req,res) {

    try{
        if(checkHasAccount(req)){

            if(checkAdmin(req)){
                const result = await Collection.find();
                res.json(result)
                return
            }
            else{
                const result = await Collection.find({
                    isApprove : true
                })
                res.json(result)
                return
            }
        }else{
            const result = await Collection.find({
                isApprove : true
            })
            res.json(result)
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}




//update collection
export async function updateCollection(req,res) {

    try{

        const id = req.params.id;
        const data = req.body

        if(checkHasAccount(req)){


            if(checkAdmin(req)){

                await Collection.updateOne({
                    _id : id
                },data)
                res.json({
                    message : "Collection Update successfully"
                })
                return
            }

            if(checkRestaurant(req)){

                

               
                    await Collection.updateOne({
                        _id : id,
                        ownerId : req.user.id
                       },{
                        name : data.name,
                        description : data.description,
                        price : data.price,
                        images : data.images,
                        category : data.category,
                       })
                       res.json({
                        message : "Collection Update successfully"
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
                message : "Login first"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}

//delete collection
export async function deleteCollection(req,res) {
    
    try{
        const id = req.params.id;

        if(checkHasAccount(req)){

            if(checkAdmin(req)){

                await Collection.deleteOne({
                    _id : id
                })
                res.json({
                    message : "Collection deleted Successfully"
                })
                return
            }

            if(checkRestaurant(req)){
                
                
                    await Collection.deleteOne({
                        _id : id,
                        ownerId : req.user.id

                    })
                    res.json({
                        message : "Collection deleted Successfully"
                    })
                    return
                
            }
            res.json({
                message : "cant access this task"
            })
        }else{
            res.json({
                message : "cant access this task"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error :  err
        })
    }
}

export async function approveItem(req,res) {

    try{

        const id = req.params.id

        if(checkHasAccount(req)){

            if(checkAdmin(req)){

                await Collection.updateOne({
                    _id : id
                },{
                    isApprove : true
                })
                res.json({
                    message : "Item Approve successfully"
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
                message : "please login first"
            })
            return
        }
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}


export async function getOne(req,res) {

    try{
        const id = req.params.id;

        const result = await Collection.findOne({
            _id : id
        })
        res.json(result)
        return
    }catch(err){
        res.status(500).json({
            error : "Internal Server error" || err
        })
    }
    
}

