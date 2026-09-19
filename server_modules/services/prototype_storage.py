"""Give each static drawing independent browser storage on the Studio origin."""
import json


def isolate_storage(html: bytes, project: str) -> bytes:
    prefix = json.dumps(f"agentforge:prototype:{project}:")
    script = """<script data-agentforge-storage>(()=>{
try {
  const prefix=PREFIX;
  for(const kind of ['localStorage','sessionStorage']){
    try {
      const storage=window[kind];
      if(!storage) continue;
      const keys=()=>Object.keys(storage).filter(key=>key.startsWith(prefix));
      const api={getItem:key=>storage.getItem(prefix+key),setItem:(key,value)=>storage.setItem(prefix+key,String(value)),
        removeItem:key=>storage.removeItem(prefix+key),clear:()=>keys().forEach(key=>storage.removeItem(key)),
        key:index=>keys()[index]?.slice(prefix.length)??null,get length(){return keys().length}};
      Object.defineProperty(window,kind,{value:new Proxy(api,{
        get:(target,key)=>key in target?target[key]:target.getItem(key),
        set:(target,key,value)=>{target.setItem(key,value);return true},
        deleteProperty:(target,key)=>{target.removeItem(key);return true},
        ownKeys:()=>keys().map(key=>key.slice(prefix.length)),
        getOwnPropertyDescriptor:()=>({enumerable:true,configurable:true})})});
    } catch(e) {}
  }
} catch(e) {}
})();</script>""".replace("PREFIX", prefix.replace("<", "\\u003c"))
    text = html.decode("utf-8", errors="replace")
    import re
    match = re.search(r"<head\b[^>]*>", text, re.I)
    at = match.end() if match else 0
    return (text[:at] + script + text[at:]).encode("utf-8")
