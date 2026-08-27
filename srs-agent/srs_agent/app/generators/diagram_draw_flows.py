"""Activity, BPMN and architecture native drawings."""
from __future__ import annotations

from .diagram_draw_primitives import *
from .diagram_draw_primitives import (
    _arrow, _clean, _diamond, _drawing, _end, _explicit_decision, _fit, _line,
    _curve_arrow, _not_applicable, _orth_arrow, _overlap, _port, _rounded, _start, _text_block, _txt,
)
from .diagram_draw_entities import *
from .diagram_draw_entities import _erd, _relations, _sequence, _use_case

def _activity(doc: dict, W: float) -> Drawing:
    workflows = doc.get("business_workflows") or []
    wf = workflows[0] if workflows else {}
    steps = [str(s) for s in (wf.get("steps") or []) if str(s).strip()][:9]
    if not steps:
        return _not_applicable(W, "Activity Diagram", "No ordered business workflow is specified in the approved SRS.")
    H = 92 + len(steps)*62 + 44
    d,g = _drawing(W,H)
    cx=W/2; y=H-34
    title=str(wf.get("workflow_name") or "Primary workflow")
    _txt(g,24,H-24,_fit(title,FB,9.4,W-48),9.4,FB,MUTED)
    _start(g,cx,y); prev=(cx,y-7)
    for step in steps:
        y-=62
        if _explicit_decision(step):
            _diamond(g,cx,y,min(170,W*.36),42,step,size=7.7)
            _arrow(g,prev[0],prev[1],cx,y+21,color=INK,sw=.95,open_head=False)
            prev=(cx,y-21)
        else:
            w=min(W*.58,300); h=38
            _rounded(g,cx-w/2,y-h/2,w,h,step,stroke=GREEN,fill=GREEN_BG,size=8.4,radius=14)
            _arrow(g,prev[0],prev[1],cx,y+h/2,color=INK,sw=.95,open_head=False)
            prev=(cx,y-h/2)
    y-=52; _end(g,cx,y); _arrow(g,prev[0],prev[1],cx,y+8,color=INK,sw=.95,open_head=False)
    d.add(g); return d


# Class & Object Diagram — UML structural.
def _class_box(g: Group, x,y,w, table: dict):
    attrs=(table.get("fields") or [])[:9]
    ops=[str(o) for o in (table.get("operations") or []) if str(o).strip()][:4]
    head=27; attr_h=max(34,14*len(attrs)+8); op_h=(14*len(ops)+10) if ops else 0; h=head+attr_h+op_h
    g.add(Rect(x,y,w,h,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=1.15))
    _line(g,x,y+h-head,x+w,y+h-head,LINE_DARK,.95)
    _txt(g,x+w/2,y+h-18,_fit(str(table.get("table_name") or "Class").replace("_"," ").title(),FB,9.1,w-12),9.1,FB,INK,"middle")
    fy=y+h-head-16
    for fld in attrs:
        vis="+" if fld.get("primary_key") else "-"
        typ=str(fld.get("type") or "String")
        if typ=="foreign_key": typ="ObjectId"
        _txt(g,x+7,fy,_fit(f"{vis} {fld.get('name','field')}: {typ}",FM,7.0,w-14),7.0,FM,INK); fy-=14
    if ops:
        sep=y+op_h; _line(g,x,sep,x+w,sep,LINE_DARK,.9); fy=sep-14
        for op in ops:
            _txt(g,x+7,fy,_fit(f"+ {op}",F,7,w-14),7,F,INK); fy-=14
    return h


def _class_object(doc: dict, W: float) -> Drawing:
    tables=[t for t in (((doc.get("database_design") or {}).get("tables") or [])[:5]) if isinstance(t,dict) and t.get("table_name")]
    if not tables:
        return _not_applicable(W, "Class & Object Diagram", "No domain/data classes are specified in the SRS.")
    rels=_relations(doc,tables)
    cols=2 if len(tables)>1 else 1; margin=20; gap=30; cw=(W-2*margin-gap*(cols-1))/cols
    # Compute actual heights without drawing.
    heights={str(t["table_name"]):27+max(34,14*min(len(t.get("fields") or []),9)+8)+((14*min(len(t.get("operations") or []),4)+10) if t.get("operations") else 0) for t in tables}
    rows=math.ceil(len(tables)/cols); row_h=max(heights.values())+38
    object_h=86
    H=44+rows*row_h+object_h+42
    d,g=_drawing(W,H); pos={}
    for i,t in enumerate(tables):
        c=i%cols; r=i//cols; x=margin+c*(cw+gap); h=heights[str(t["table_name"])]
        y=H-38-(r+1)*row_h+(row_h-h)/2
        pos[str(t["table_name"])]=(x,y,cw,h)
    # Associations behind boxes
    for rel in rels[:8]:
        a,b=rel["from"],rel["to"]
        if a not in pos or b not in pos: continue
        ax,ay,aw,ah=pos[a]; bx,by,bw,bh=pos[b]
        if ax<bx: x1,y1=ax+aw,ay+ah/2; x2,y2=bx,by+bh/2
        elif ax>bx: x1,y1=ax,ay+ah/2; x2,y2=bx+bw,by+bh/2
        else: x1,y1=ax+aw/2,ay; x2,y2=bx+bw/2,by+bh
        _orth_arrow(g,x1,y1,x2,y2,color=LINE_DARK,sw=.85,head=False)
        typ=rel.get("type") or ""
        mult={"one_to_many":("1","0..*"),"many_to_one":("0..*","1"),"one_to_one":("1","1"),"many_to_many":("0..*","0..*")}.get(typ,("",""))
        if mult[0]: _txt(g,x1+4,y1+4,mult[0],6.8,F,MUTED)
        if mult[1]: _txt(g,x2+4,y2+4,mult[1],6.8,F,MUTED)
    for t in tables:
        x,y,w,h=pos[str(t["table_name"])]
        _class_box(g,x,y,w,t)

    _txt(g,W/2,object_h+24,"Object snapshot (illustrative instance)",7.6,F,MUTED,"middle")
    t=tables[0]; ow=min(250,W*.46); ox=(W-ow)/2; oy=20; attrs=(t.get("fields") or [])[:3]; oh=36+15*max(1,len(attrs))
    g.add(Rect(ox,oy,ow,oh,fillColor=GREEN_BG,strokeColor=GREEN,strokeWidth=1.15))
    name=f"example : {str(t.get('table_name') or 'Class').replace('_',' ').title()}"
    label=_fit(name,FB,8.1,ow-14); _txt(g,ox+ow/2,oy+oh-18,label,8.1,FB,INK,"middle")
    tw=stringWidth(label,FB,8.1); _line(g,ox+ow/2-tw/2,oy+oh-20,ox+ow/2+tw/2,oy+oh-20,INK,.65)
    _line(g,ox,oy+oh-27,ox+ow,oy+oh-27,GREEN,.8)
    fy=oy+oh-42
    for fld in attrs:
        val=fld.get("default")
        if val is None and fld.get("values"): val=fld["values"][0]
        if val is None: val=f"<{fld.get('type','value')}>"
        _txt(g,ox+8,fy,_fit(f"{fld.get('name','field')} = {val}",FM,7.1,ow-16),7.1,FM,INK); fy-=15
    d.add(g); return d


# State Machine — UML behavioral.
def _state_machine(doc: dict, W: float) -> Drawing:
    from .diagram_sources_arch import _first_lifecycle, _state_transitions
    life=_first_lifecycle(doc); transitions=_state_transitions(doc,life) if life else []
    if not life or not transitions:
        return _not_applicable(W,"State Machine Diagram",
            "The SRS does not define legal state-to-state transitions. A professional state machine is omitted rather than inventing a lifecycle.")
    states=[str(s) for s in life.get("states") or []]
    n=len(states); node_w=min(124,max(88,(W-110)/max(n,1)*.75)); gap=(W-84)/max(n,1)
    H=250; d,g=_drawing(W,H); y=122; pos={}
    _txt(g,22,H-26,_fit(f"{life.get('entity','Entity')} · {life.get('field','status')} lifecycle",FB,9,W-44),9,FB,MUTED)
    for i,state in enumerate(states):
        cx=42+gap*(i+.5); _rounded(g,cx-node_w/2,y-19,node_w,38,state,stroke=GREEN,fill=GREEN_BG,size=8.1,radius=16); pos[state]=(cx,node_w)
    first=transitions[0][0]; _start(g,22,y); _arrow(g,29,y,pos[first][0]-pos[first][1]/2,y,color=INK,sw=.95,open_head=False)
    reverse_lane=0
    for a,b,label in transitions:
        if a not in pos or b not in pos: continue
        ax,aw=pos[a]; bx,bw=pos[b]
        if ax<bx:
            _arrow(g,ax+aw/2,y,bx-bw/2,y,color=INK,sw=.9,label=_fit(label,F,6.8,max(72,bx-ax-aw/2-bw/2)),open_head=True,label_size=6.6)
        else:
            reverse_lane+=1; top=y+48+reverse_lane*16
            _line(g,ax,y+19,ax,top,INK,.85); _line(g,ax,top,bx,top,INK,.85)
            _arrow(g,bx,top,bx,y+19,color=INK,sw=.85,label=_fit(label,F,6.5,100),open_head=True,label_size=6.4)
    outgoing={a for a,_,_ in transitions}; finals=[s for s in states if s not in outgoing]
    if finals:
        end_state=finals[-1]; ex=min(W-22,pos[end_state][0]+pos[end_state][1]/2+34); _end(g,ex,y)
        _arrow(g,pos[end_state][0]+pos[end_state][1]/2,y,ex-8,y,color=INK,sw=.9,open_head=False)
    d.add(g); return d


# DFD — Yourdon/DeMarco style.
def _dfd_store(g: Group,x,y,w,h,label):
    _line(g,x,y+h,x+w,y+h,ORANGE,1.05); _line(g,x,y,x+w,y,ORANGE,1.05)
    _line(g,x+30,y,x+30,y+h,ORANGE,.85)
    _txt(g,x+15,y+h/2-3,label.split(":",1)[0],7.0,FB,ORANGE,"middle")
    rest=label.split(":",1)[1].strip() if ":" in label else label
    _text_block(g,x+30+(w-30)/2,y+h/2,rest,maxw=w-40,size=7.4,max_lines=2)


def _process_name(module: str) -> str:
    m=_clean(module).replace("_"," ")
    if re.search(r"management$",m,re.I):
        base=re.sub(r"management$","",m,flags=re.I).strip(); return f"Manage {base}" if base else "Management"
    return m


def _dfd_flow_names(action: str) -> tuple[str, str]:
    """Turn an action/use-case label into short, named DFD data flows.

    A DFD arrow carries data, not the full control/action sentence.  Keeping the
    derivation generic also prevents hotel- or shop-specific labels leaking into
    diagrams for unrelated generated applications.
    """
    text=_clean(action)
    first=(text.split() or ["process"])[0].lower().strip(" ,:-")
    read_verbs={"search","find","view","list","get","check","compare","review","inspect","browse"}
    write_verbs={"create","add","book","register","update","edit","change","manage","record","submit","apply","cancel","deactivate","delete","remove","pay","assign"}
    # Prefer the first object phrase and stop before qualifiers or a second action.
    tail=re.sub(r"^[A-Za-z0-9_-]+[,:-]?\s*", "", text).strip()
    primary=re.split(r"\s+(?:by|for|with|using|and\s+(?:create|add|apply|update|edit|change|manage|record|submit|cancel|deactivate|delete|remove|pay|assign))\b",tail,1,flags=re.I)[0]
    primary=re.sub(r"^(?:all|a|an|the|their|own)\s+", "", primary, flags=re.I).strip(" ,:-")
    if not primary or re.fullmatch(r"(?:edit|change|update)",primary,re.I):
        ignored={"create","add","book","register","update","edit","change","manage","record","submit","apply","cancel","deactivate","delete","remove","pay","assign","and","all","a","an","the","their","own"}
        words=[w for w in re.findall(r"[A-Za-z0-9-]+",tail) if w.lower() not in ignored]
        primary=" ".join(words[-2:]) or "record"
    object_name=" ".join(primary.split()[:2]).lower()
    if first in read_verbs:
        return (f"{first} criteria", object_name)
    if first in write_verbs:
        noun={"book":"booking","pay":"payment","register":"registration"}.get(first,first)
        request=f"{noun} details" if first in {"book","pay","register"} else f"{object_name} changes"
        return (request, f"{object_name} status")
    return (f"{object_name} input", f"{object_name} result")


def _dfd(doc: dict, W: float) -> Drawing:
    from .diagrams import actors_and_use_cases
    actors,cases=actors_and_use_cases(doc)
    actors=actors[:4]
    case_label={c["id"]:c["label"] for c in cases}
    raw_modules=[_process_name(str(m)) for m in (doc.get("main_modules") or []) if str(m).strip()]
    modules=[]
    # Actor goals are business processes; page/module names are only a fallback.
    # Taking the first five UI modules produced a control-flow-looking DFD and
    # sent later roles into unrelated processes.
    for actor in actors:
        goals=[case_label.get(uid,"") for uid in actor.get("does",[]) if case_label.get(uid,"")]
        if goals and goals[0] not in modules: modules.append(goals[0])
    if not modules:
        modules=raw_modules[:5]
    if not modules:
        modules=[_clean(s.get("name")) for s in ((doc.get("effective_plan") or doc.get("approved_plan") or {}).get("screens") or []) if s.get("name")][:4]
    all_stores=[str(t.get("table_name")) for t in (((doc.get("database_design") or {}).get("tables") or [])[:10]) if t.get("table_name")]
    if not modules:
        return _not_applicable(W,"Data Flow Diagram","No processes/modules are specified from which to derive a data-flow view.")
    # Show only stores used by this DFD process.
    stores=[t for t in all_stores if max((_overlap(t,m) for m in modules), default=0) > 0]
    if not stores:
        stores=all_stores[:3]
    stores=stores[:6]
    proc_x=W*.48; store_x=W-145; ext_x=18
    row_gap=82; H=max(300,70+max(len(modules),len(actors),len(stores))*row_gap)
    d,g=_drawing(W,H)
    actor_pos={}; proc_pos={}; store_pos={}
    for i,m in enumerate(modules):
        y=H-62-i*row_gap; proc_pos[i]=(proc_x,y)
        g.add(Ellipse(proc_x,y,64,30,fillColor=GREEN_BG,strokeColor=GREEN,strokeWidth=1.2))
        _text_block(g,proc_x,y,f"{i+1}.0 {_process_name(m)}",maxw=108,size=7.6,max_lines=2)

    actor_targets={}
    actor_flow_labels={}
    for a in actors:
        goal_rows=[case_label.get(uid,"") for uid in a.get("does",[]) if case_label.get(uid,"")]
        goals=" ".join(goal_rows)
        scores=[(_overlap(goals,m),i) for i,m in enumerate(modules)]
        _,pi=max(scores,default=(0,0)); actor_targets[a["id"]]=pi
        actor_flow_labels[a["id"]]=_dfd_flow_names(goal_rows[0] if goal_rows else modules[pi])
    actor_counts={}
    actor_totals=defaultdict(int)
    for pi in actor_targets.values(): actor_totals[pi]+=1
    for a in actors:
        pi=actor_targets[a["id"]]; px,py=proc_pos[pi]
        n=actor_counts.get(pi,0); actor_counts[pi]=n+1
        offset=(n-(actor_totals[pi]-1)/2)*42
        port_offset=(n-(actor_totals[pi]-1)/2)*10
        ay=max(34,min(H-34,py+offset))
        actor_pos[a["id"]]=(ext_x,ay-18,95,36)
        g.add(Rect(ext_x,ay-18,95,36,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=1.1))
        _text_block(g,ext_x+47.5,ay,a["label"],maxw=82,size=8.0,font=FB,max_lines=2)
        request_flow,result_flow=actor_flow_labels[a["id"]]
        _arrow(g,ext_x+95,ay+7,px-64,py+7+port_offset,color=INK,sw=.85,
               label=request_flow,open_head=True,label_size=5.8)
        _arrow(g,px-64,py-7+port_offset,ext_x+95,ay-7,color=INK,sw=.8,
               label=result_flow,open_head=True,label_size=5.8)

    store_candidates=[]
    for i,t in enumerate(stores):
        scores=[(_overlap(t,m),pi) for pi,m in enumerate(modules)]
        score,pi=max(scores,default=(0,min(i,len(modules)-1)))
        if score==0: pi=min(i,len(modules)-1)
        store_candidates.append((t,pi,score))
    # A compact level-1 DFD becomes unreadable when every related table fans out
    # from the same process. Keep the strongest store relationship per process
    # (two when the diagram itself has only one or two processes).
    store_limit=2 if len(modules)<=2 else 1
    selected=[]
    for pi in range(len(modules)):
        ranked=sorted((c for c in store_candidates if c[1]==pi),
                      key=lambda c:(-c[2],len(c[0])))
        selected.extend(ranked[:store_limit])
    stores=[c[0] for c in selected]
    store_targets=[c[1] for c in selected]
    store_counts={}
    store_totals=defaultdict(int)
    for pi in store_targets: store_totals[pi]+=1
    for i,t in enumerate(stores):
        pi=store_targets[i]; px,py=proc_pos[pi]
        n=store_counts.get(pi,0); store_counts[pi]=n+1
        offset=(n-(store_totals[pi]-1)/2)*48
        port_offset=(n-(store_totals[pi]-1)/2)*14
        sy=max(34,min(H-34,py+offset))
        store_pos[i]=(store_x,sy)
        _dfd_store(g,store_x,sy-17,127,34,f"D{i+1}: {t.replace('_',' ').title()}")
        data_name=t.replace("_"," ").strip()
        _arrow(g,px+64,py+7+port_offset,store_x,sy+7,color=INK,sw=.85,
               label=f"{data_name} record",open_head=True,label_size=5.8)
        _arrow(g,store_x,sy-7,px+64,py-7+port_offset,color=INK,sw=.8,
               label=f"{data_name} data",open_head=True,label_size=5.8)
    d.add(g); return d


# BPMN 2.0 core process view.
def _step_lane(step: str, roles: list[str], previous: str | None) -> str:
    for r in roles:
        tokens=[t for t in re.findall(r"[A-Za-z0-9]+",r) if len(t)>2 and t.lower() not in {"user","role"}]
        if re.search(rf"\b{re.escape(r)}\b",step,re.I) or any(
                re.search(rf"\b{re.escape(t)}\b",step,re.I) for t in tokens):
            return r
    if re.search(r"\b(system|application|platform|service|api)\b",step,re.I): return "System"
    first=(str(step).strip().split() or [""])[0].strip(" :,-")
    if first and first[:1].isupper() and first.lower() not in {"create","update","view","manage","process","record"}:
        return first
    return previous or (roles[0] if roles else "Process")


def _bpmn_task_label(step: str, lane: str) -> str:
    """Remove the redundant participant subject; the lane already owns it."""
    text=_clean(step)
    candidates=[lane]+[t for t in re.findall(r"[A-Za-z0-9]+",lane) if len(t)>2]
    for subject in candidates:
        shortened=re.sub(rf"^{re.escape(subject)}\s+", "", text, count=1, flags=re.I)
        if shortened != text:
            return shortened[:1].upper()+shortened[1:]
    return text


def _bpmn(doc: dict, W: float) -> Drawing:
    workflows=doc.get("business_workflows") or []; wf=workflows[0] if workflows else {}
    steps=[str(s) for s in (wf.get("steps") or []) if str(s).strip()][:9]
    if not steps:
        return _not_applicable(W,"BPMN Process Diagram","No business process steps are specified in the SRS.")
    roles=[str(r.get("role_name") or r.get("role_key")) for r in (doc.get("roles") or []) if r.get("role_name") or r.get("role_key")]
    lane_for=[]; prev=None
    for s in steps:
        prev=_step_lane(s,roles,prev); lane_for.append(prev)
    lanes=[]
    for l in lane_for:
        if l not in lanes: lanes.append(l)
    lanes=lanes[:4] or ["Process"]
    # Any trimmed role maps to the last visible lane.
    lane_for=[l if l in lanes else lanes[-1] for l in lane_for]
    lane_h=104; y0=18; title_h=42
    pool_h=max(1,len(lanes))*lane_h; H=pool_h+title_h+34
    d,g=_drawing(W,H)
    x0=18; pw=W-36; label_w=88; pool_top=y0+pool_h
    g.add(Rect(x0,y0,pw,pool_h,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=1.15))
    _line(g,x0+label_w,y0,x0+label_w,pool_top,LINE_DARK,.8)
    for i,lane in enumerate(lanes):
        lane_top=pool_top-i*lane_h
        lane_bottom=lane_top-lane_h
        if i: _line(g,x0,lane_top,x0+pw,lane_top,LINE_DARK,.8)
        _text_block(g,x0+label_w/2,(lane_top+lane_bottom)/2,lane,
                    maxw=label_w-12,size=7.6,font=FB,max_lines=2)
    _txt(g,x0,H-20,_fit(str(wf.get("workflow_name") or "Business process"),FB,9.2,pw),9.2,FB,MUTED)
    _txt(g,x0+label_w/2,pool_top+7,"POOL / LANES",6.4,FB,MUTED,"middle")

    content_left=x0+label_w+20; content_right=x0+pw-20
    gap=(content_right-content_left)/max(2,len(steps)+1)
    def lane_y(name):
        return pool_top-(lanes.index(name)+.5)*lane_h

    sy=lane_y(lane_for[0]); sx=content_left
    g.add(Circle(sx,sy,8,fillColor=WHITE,strokeColor=GREEN,strokeWidth=1.5)); prev_pt=(sx+8,sy)
    for i,step in enumerate(steps):
        lane=lane_for[i]; cx=content_left+(i+1)*gap; cy=lane_y(lane)
        if _explicit_decision(step):
            dw=min(66,max(44,gap*.72)); dh=42
            _diamond(g,cx,cy,dw,dh,step,stroke=ORANGE,fill=WHITE,size=5.9)
            left,right=cx-dw/2,cx+dw/2
        else:
            tw=min(112,max(56,gap*.92)); th=70
            _rounded(g,cx-tw/2,cy-th/2,tw,th,_bpmn_task_label(step,lane),
                     stroke=LINE_DARK,fill=BLUE_BG,size=6.2,radius=7,max_lines=5)
            left,right=cx-tw/2,cx+tw/2
        _orth_arrow(g,prev_pt[0],prev_pt[1],left,cy,via_x=(prev_pt[0]+left)/2,
                    color=INK,sw=.9,open_head=True)
        prev_pt=(right,cy)
    end_x=content_right; end_y=lane_y(lane_for[-1])
    g.add(Circle(end_x,end_y,10,fillColor=WHITE,strokeColor=BLACK,strokeWidth=2.2))
    _orth_arrow(g,prev_pt[0],prev_pt[1],end_x-10,end_y,via_x=(prev_pt[0]+end_x-10)/2,
                color=INK,sw=.9,open_head=True)
    d.add(g); return d


def _context(doc: dict, W: float) -> Drawing:
    from .diagrams import actors_and_use_cases
    actors,_=actors_and_use_cases(doc); actors=actors[:5]
    integrations=(doc.get("integration_requirements") or [])[:5]
    modules=[str(m) for m in (doc.get("main_modules") or []) if str(m).strip()][:6]
    tables=((doc.get("database_design") or {}).get("tables") or [])
    has_db=bool(tables)
    H=max(360,150+max(len(actors),len(integrations))*66)
    d,g=_drawing(W,H); cx,cy=W/2,H/2+12
    sw=min(250,W*.39); sh=126

    # System boundary + central system. The boundary gives every external
    # relationship an unambiguous inside/outside meaning.
    g.add(Rect(cx-sw/2-16,cy-sh/2-18,sw+32,sh+36,rx=12,ry=12,
               fillColor=WHITE,strokeColor=LINE,strokeWidth=.9))
    _txt(g,cx-sw/2-6,cy+sh/2+8,"SYSTEM BOUNDARY",6.6,FB,MUTED)
    g.add(Rect(cx-sw/2,cy-sh/2,sw,sh,rx=10,ry=10,fillColor=PURPLE_BG,strokeColor=PURPLE,strokeWidth=1.5))
    _text_block(g,cx,cy+30,doc.get("project_name","System"),maxw=sw-24,size=10.4,font=FB,max_lines=2)
    kind=(doc.get("app_type") or {}).get("primary_type") or "Application"
    _txt(g,cx,cy+2,_fit(kind,F,7.6,sw-24),7.6,F,MUTED,"middle")
    if modules:
        _txt(g,cx,cy-20,"Core capabilities",6.6,FB,MUTED,"middle")
        shown=" · ".join(modules[:4])
        _text_block(g,cx,cy-39,shown,maxw=sw-26,size=6.9,color=INK,max_lines=2)

    left_ports=[]
    for i,a in enumerate(actors):
        y=H-62-i*66; w=120; x=18
        g.add(Rect(x,y-20,w,40,rx=7,ry=7,fillColor=GREEN_BG,strokeColor=GREEN,strokeWidth=1.0))
        _text_block(g,x+w/2,y,a["label"],maxw=w-12,size=8.0,font=FB,max_lines=2)
        py=cy+sh/2-22-i*(max(14,(sh-42)/max(1,len(actors)-1))) if len(actors)>1 else cy
        py=max(cy-sh/2+18,min(cy+sh/2-18,py)); left_ports.append(py)
        _curve_arrow(g,x+w,y,cx-sw/2,py,color=LINE_DARK,sw=.9,label="uses",open_head=True,label_size=6.4)

    for i,integ in enumerate(integrations):
        y=H-62-i*66; w=138; x=W-18-w
        g.add(Rect(x,y-20,w,40,rx=7,ry=7,fillColor=ORANGE_BG,strokeColor=ORANGE,strokeWidth=1.0))
        _text_block(g,x+w/2,y,integ.get("name","External system"),maxw=w-12,size=7.9,font=FB,max_lines=2)
        py=cy+sh/2-22-i*(max(14,(sh-42)/max(1,len(integrations)-1))) if len(integrations)>1 else cy
        py=max(cy-sh/2+18,min(cy+sh/2-18,py))
        _curve_arrow(g,cx+sw/2,py,x,y,color=LINE_DARK,sw=.9,label="API / event",open_head=True,label_size=6.2)

    if has_db:
        dw=170; dx=cx-dw/2; dy=26
        g.add(Rect(dx,dy,dw,38,fillColor=BLUE_BG,strokeColor=BLUE,strokeWidth=1.0))
        g.add(Ellipse(cx,dy+38,dw/2,8,fillColor=BLUE_BG,strokeColor=BLUE,strokeWidth=1.0))
        g.add(Ellipse(cx,dy,dw/2,8,fillColor=BLUE_BG,strokeColor=BLUE,strokeWidth=1.0))
        names=[str(t.get("table_name") or "") for t in tables[:4] if isinstance(t,dict)]
        _txt(g,cx,dy+20,"Persistent application data",8.0,FB,INK,"middle")
        if names: _txt(g,cx,dy+7,_fit(" · ".join(names),F,6.4,dw-18),6.4,F,MUTED,"middle")
        _curve_arrow(g,cx,cy-sh/2,cx,dy+46,color=LINE_DARK,sw=.9,label="reads / writes",open_head=True,label_size=6.4)
    d.add(g); return d


def _component_marker(g: Group, x: float, y: float, w: float, h: float):
    tabw,tabh=12,7
    g.add(Rect(x+8,y+h-16,tabw,tabh,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=.8))
    g.add(Rect(x+8,y+h-27,tabw,tabh,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=.8))


def _component_box(g: Group,x,y,w,h,label,fill=BLUE_BG,stroke=BLUE):
    g.add(Rect(x,y,w,h,fillColor=fill,strokeColor=stroke,strokeWidth=1.05))
    _component_marker(g,x,y,w,h)
    _text_block(g,x+w/2+6,y+h/2,label,maxw=w-34,size=7.7,font=FB,max_lines=2)


def _component_port(g: Group, x: float, y: float):
    g.add(Rect(x-3,y-3,6,6,fillColor=WHITE,strokeColor=LINE_DARK,strokeWidth=.9))


def _component(doc: dict, W: float) -> Drawing:
    plan=doc.get("effective_plan") or doc.get("approved_plan") or {}
    screens=[str(s.get("name")) for s in (plan.get("screens") or []) if s.get("name")][:6]
    if not screens:
        screens=[str(p.get("page_name")) for p in (doc.get("public_pages") or [])+(doc.get("protected_pages") or []) if p.get("page_name")][:6]
    modules=[str(m) for m in (doc.get("main_modules") or []) if str(m).strip()][:7]
    stores=[str(t.get("table_name")) for t in (((doc.get("database_design") or {}).get("tables") or [])[:6]) if t.get("table_name")]
    integrations=[str(i.get("name")) for i in (doc.get("integration_requirements") or []) if i.get("name")][:3]
    if not (screens or modules):
        return _not_applicable(W,"Component Diagram","No presentation or application modules are specified in the SRS.")
    screens=screens or ["User interface"]; modules=modules or ["Application core"]
    row_h=110; H=360; d,g=_drawing(W,H)
    bands=[("Presentation",250,BLUE_BG,BLUE),("Application / Domain",140,GREEN_BG,GREEN),("Data & External Interfaces",30,ORANGE_BG,ORANGE)]
    for label,y,fill,stroke in bands:
        g.add(Rect(14,y-4,W-28,row_h-4,fillColor=fill,strokeColor=LINE,strokeWidth=.8))
        _txt(g,24,y+row_h-25,label,8.2,FB,MUTED)
    def place(items,y,kind):
        count=max(1,len(items)); gap=12; avail=W-56; bw=min(142,(avail-gap*(count-1))/count); total=bw*count+gap*(count-1); start=(W-total)/2; pos=[]
        for i,item in enumerate(items):
            x=start+i*(bw+gap); h=44
            if kind=="component": _component_box(g,x,y,bw,h,item)
            else:
                g.add(Rect(x,y,bw,h,fillColor=WHITE,strokeColor=ORANGE if kind=="external" else LINE_DARK,strokeWidth=1.0))
                _text_block(g,x+bw/2,y+h/2,item,maxw=bw-12,size=7.5,font=FB,max_lines=2)
            pos.append((x,y,bw,h,item))
        return pos
    s_pos=place(screens[:5],276,"component")
    m_pos=place(modules[:5],166,"component")
    bottom_items=stores[:4]+integrations[:2]
    b_pos=place(bottom_items[:6],56,"external") if bottom_items else []
    for i,s in enumerate(s_pos):
        scores=[(_overlap(s[4],m[4]),j) for j,m in enumerate(m_pos)]; score,j=max(scores,default=(0,i%len(m_pos))); j=j if score>0 else i%len(m_pos); m=m_pos[j]
        sx,sy=s[0]+s[2]/2,s[1]; mx,my=m[0]+m[2]/2,m[1]+m[3]
        _component_port(g,sx,sy); _component_port(g,mx,my)
        _curve_arrow(g,sx,sy,mx,my,color=LINE_DARK,sw=.8,label="requires",
                     open_head=True,label_size=5.9,ports=False)
    for i,b in enumerate(b_pos):
        scores=[(_overlap(b[4],m[4]),j) for j,m in enumerate(m_pos)]
        score,j=max(scores,default=(0,i%len(m_pos))); j=j if score>0 else i%len(m_pos)
        m=m_pos[j]; mx,my=m[0]+m[2]/2,m[1]; bx,by=b[0]+b[2]/2,b[1]+b[3]
        _component_port(g,mx,my); _component_port(g,bx,by)
        _curve_arrow(g,mx,my,bx,by,color=LINE_DARK,sw=.8,label="data / API",
                     open_head=True,label_size=5.9,ports=False)
    d.add(g); return d


def _deployment_node(g: Group,x,y,w,h,title,stereotype,items=None,fill=PANEL):
    # UML node-like box with a shallow offset top/right edge.
    off=7
    g.add(Rect(x+off,y+off,w,h,fillColor=colors.HexColor("#E8EDF1"),strokeColor=LINE,strokeWidth=.7))
    g.add(Rect(x,y,w,h,fillColor=fill,strokeColor=LINE_DARK,strokeWidth=1.05))
    _txt(g,x+10,y+h-17,f"«{stereotype}»",6.8,F,MUTED)
    _txt(g,x+10,y+h-32,_fit(title,FB,8.4,w-20),8.4,FB,INK)
    fy=y+h-50
    for item in (items or [])[:3]:
        _txt(g,x+16,fy,_fit(f"• {item}",F,7,w-24),7,F,INK); fy-=13


def _deployment(doc: dict, W: float) -> Drawing:
    stack=(doc.get("app_type") or {}).get("example_stack") or {}
    frontend=str(stack.get("frontend") or "Web client")
    backend=str(stack.get("backend") or "Application/API")
    database=str(stack.get("database") or "Database")
    integrations=[str(i.get("name")) for i in (doc.get("integration_requirements") or []) if i.get("name")][:3]
    H=300; d,g=_drawing(W,H)
    margin=24; gap=28; w=(W-2*margin-2*gap)/3; y=108; h=112
    _deployment_node(g,margin,y,w,h,"Client Device","device",["Browser / mobile web"])
    _deployment_node(g,margin+w+gap,y,w,h,"Application Host","executionEnvironment",[frontend,backend])
    _deployment_node(g,margin+2*(w+gap),y,w,h,"Database Host","executionEnvironment",[database])
    _curve_arrow(g,margin+w,y+h/2,margin+w+gap,y+h/2,color=LINE_DARK,sw=.9,label="HTTPS",open_head=True,label_size=6.7)
    _curve_arrow(g,margin+2*w+gap,y+h/2,margin+2*(w+gap),y+h/2,color=LINE_DARK,sw=.9,label="database connection",open_head=True,label_size=6.4)
    if integrations:
        count=len(integrations); bw=min(150,(W-48-(count-1)*16)/count); total=count*bw+(count-1)*16; start=(W-total)/2
        for i,name in enumerate(integrations):
            x=start+i*(bw+16); by=28
            g.add(Rect(x,by,bw,44,fillColor=ORANGE_BG,strokeColor=ORANGE,strokeWidth=1.0))
            _text_block(g,x+bw/2,by+22,name,maxw=bw-12,size=7.6,font=FB,max_lines=2)
            host_cx=margin+w+gap+w/2
            _curve_arrow(g,host_cx,y,x+bw/2,by+44,color=LINE_DARK,sw=.8,label="API / integration",open_head=True,label_size=6.2)
    d.add(g); return d


_RENDERERS = {
    "use_case": _use_case,
    "sequence": _sequence,
    "erd": _erd,
    "activity": _activity,
    "class_object": _class_object,
    "state_machine": _state_machine,
    "dfd": _dfd,
    "bpmn": _bpmn,
    "system_context": _context,
    "component": _component,
    "deployment": _deployment,
}


def render_native(kind: str, doc: dict, width: float) -> Optional[Drawing]:
    fn=_RENDERERS.get(kind)
    if not fn:
        return None
    try:
        return fn(doc,width)
    except Exception:
        # A drawing failure must not discard the SRS.
        return None
