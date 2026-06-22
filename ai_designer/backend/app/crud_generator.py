"""CRUD generator orchestrator.

Given a planned data model it produces a complete, buildable, relationship-aware
full-stack slice for a Next.js + MongoDB project:

    src/lib/orm.js                              (runtime)
    src/lib/models/<Entity>.js, index.js        (schema descriptors)
    src/lib/services/<Entity>Service.js         (workflow + side effects)
    src/app/api/<collection>/route.js, [id]/route.js   (relation-aware API)
    src/components/CrudForm.jsx + (app)/manage/...     (relation-aware UI)

`generate_crud(model)` returns the file map + a sidebar manifest; `write_crud`
writes them into a project directory.
"""
from __future__ import annotations

import os

from app import mongoose_schema_generator as schema
from app import api_route_generator as api
from app import workflow_service_generator as svc
from app import crud_ui_generator as ui


def generate_crud(model: dict) -> dict:
    files = {}
    files["src/lib/orm.js"] = schema.ORM_RUNTIME
    files["src/lib/apiAuth.js"] = api.API_AUTH_HELPER

    for entity in model["entities"]:
        name = entity["name"]
        coll = entity["collection"]
        files[f"src/lib/models/{name}.js"] = schema.generate_model_file(entity, model)
        files[f"src/lib/services/{name}Service.js"] = svc.generate_service_file(entity, model)
        files[f"src/app/api/{coll}/route.js"] = api.generate_collection_route(entity)
        files[f"src/app/api/{coll}/[id]/route.js"] = api.generate_item_route(entity)

    files["src/lib/models/index.js"] = schema.generate_models_index(model)
    files.update(ui.generate_crud_ui_files())

    sidebar = [{"label": e["label"], "href": f"/manage/{e['collection']}", "collection": e["collection"]}
               for e in model["entities"]]
    return {
        "files": files,
        "sidebar": sidebar,
        "entity_names": [e["name"] for e in model["entities"]],
        "collections": [e["collection"] for e in model["entities"]],
    }


def write_crud(out_dir: str, model: dict) -> dict:
    bundle = generate_crud(model)
    written = []
    for rel, content in bundle["files"].items():
        path = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)
    bundle["written"] = written
    return bundle
