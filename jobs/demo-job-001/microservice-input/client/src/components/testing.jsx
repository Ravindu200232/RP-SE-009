import { useState } from "react"
import mediaUpload from "../utils/mediaUpload";

export default function Testing(){

    const [file,setFile] = useState(null);

    function uploadFile(){
        mediaUpload(file).then((url)=>{
            console.log(url)
        })
    }
   

    return(
        <div>
            <input type="file" multiple onChange={(e)=>{
                setFile(e.target.files[0])
            }}></input>
            <button className="w-[200px] h-[50px] bg-blue-500  text-white py-2 rounded-lg hover:bg-blue-600 transition" onClick={uploadFile}>
                Upload
            </button>
        </div>
    )
}