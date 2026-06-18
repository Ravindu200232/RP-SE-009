"""Reproduce the route-collision build failure from the hotel run and prove the
fix: Home x2 + a 'dashboard'-slug page must NOT break `next build`."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import graph, nextgen

bad = [
    {"name": "Home", "slug": "home", "template": "about", "sections": ["hero", "split", "cta"]},
    {"name": "Home", "slug": "home", "template": "about", "sections": ["hero", "cta"]},
    {"name": "Rooms & Suites", "slug": "rooms-suites", "template": "gallery", "sections": ["hero", "gallery", "pricing", "cta"]},
    {"name": "Staff Dashboard", "slug": "dashboard", "template": "features", "sections": ["hero", "features", "cta"]},
    {"name": "hotel galary", "slug": "hotel-galary", "template": "gallery", "sections": ["hero", "gallery"]},
]
safe = graph._safe_marketing_pages(bad)
slugs = [p["slug"] for p in safe]
print("safe slugs:", slugs)
assert "dashboard" not in slugs and "home" not in slugs and len(slugs) == len(set(slugs)), "sanitizer failed"

OUT = os.path.join("output", "prj_routes_test")
ents = [{"name": "RoomInventory", "label": "Rooms", "slug": "rooms", "icon": "Package", "crud_layout": "kanban",
         "fields": [{"name": "room_no", "label": "Room No", "type": "text"}, {"name": "status", "label": "Status", "type": "select", "options": ["Free", "Booked"]}]}]
links = [{"label": "Home", "href": "/"}] + [{"label": p["name"], "href": "/" + p["slug"]} for p in safe]
side = [{"label": "Dashboard", "href": "/dashboard", "icon": "LayoutDashboard"}, {"label": "Rooms", "href": "/e/rooms", "icon": "Package"}]
nextgen.create_project(OUT)
nextgen.write_status(OUT, "pages", "t")
nextgen.write_site(OUT, "Grand Stay", "Stay better.", links, side, ents, ["Manager", "Receptionist"],
                   {"nav": "pill", "footer": "soft", "dash": "band", "list": "airy"}, True)
nextgen.write_theme(OUT, "indigo", "Space Grotesk", "Inter", "glassmorphism")
nextgen.write_layout_meta(OUT, "Grand Stay", "Stay better.",
                          "https://fonts.googleapis.com/css2?family=Space+Grotesk&family=Inter&display=swap", "glassmorphism")
bp = {"domain": "hotel", "key_features": ["Online booking", "Housekeeping", "Channel manager"], "image_subjects": ["hotel room", "lobby"]}
nextgen.write_marketing_pages(OUT, safe, "Grand Stay", bp)
nextgen.write_db(OUT, {"users": [{"id": "1", "name": "M", "email": "m@m.com", "password": "x", "role": "Manager"}],
                       "RoomInventory": [{"id": "1", "room_no": "101", "status": "Free"}]})
print("building...")
ok, o = nextgen.run_build(OUT)
print("BUILD", "OK" if ok else "FAILED")
if not ok:
    print(o[-1500:])
