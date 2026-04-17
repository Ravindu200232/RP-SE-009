
export function checkHasAccount(req){

    let isTrue = false
    if(req.user){
        isTrue = true
    }
    return isTrue
}

export function checkAdmin(req){

    let isTrue = false
    if(req.user.role == "admin"){
        isTrue = true
    }
    return isTrue
}

export function checkCustomer(req){
    let isTrue = false
    if(req.user.role == "customer"){
        isTrue = true
    }
    return isTrue
}

export function checkRestaurant(req){
    let isTrue = false
    if(req.user.role == "restaurant"){
        isTrue = true
    }
    return isTrue
}

export function checkDelivery(req){
    let isTrue = false
    if(req.user.role == "delivery"){
        isTrue = true
    }
    return isTrue
}