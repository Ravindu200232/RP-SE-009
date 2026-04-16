import { createClient } from "@supabase/supabase-js"

const anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpdGh0c2dlenJnb2JkeWxvbGRiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzk5NTUzMzAsImV4cCI6MjA1NTUzMTMzMH0.NbKShjJ6vuO_1kaZ2nOYa1t1R3dUeN5msPpqKe2vRSE"
const supabase_url = "https://vithtsgezrgobdyloldb.supabase.co"

const supabase = createClient(supabase_url,anon_key)

   

export default function mediaUpload(file){


    return new Promise((resolve,reject)=>{


    if(file == null){
        reject("no file selected")
    }else{

        const timestamp = new Date().getTime();
        const fileName = timestamp + file.name
        supabase.storage.from("images").upload(fileName,file, {
        cacheControl: '3600',
        upsert: false,
        }).then(()=>{
        const publicUrl = supabase.storage.from("images").getPublicUrl(fileName).data.publicUrl;
        resolve(publicUrl)
        }).catch(()=>{
        reject("Error uploading file")
        })

    }
    

    });


    
}