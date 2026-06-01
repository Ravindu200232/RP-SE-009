from typing import TypedDict, List, Dict, Any

class GraphState(TypedDict):
    srs_input: str           #input 
    microservices: List[Dict] #list of microservices
    development_plan: str     #development plan
    generated_images: List[str] #list of generated images
    frontend_code: str       #frontend code
    user_feedback: str       #user feedback
    is_approved: bool        #user approval
    backend_code:Dict[str, str] #backend code
    

