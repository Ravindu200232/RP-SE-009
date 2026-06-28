"""Part of the `crud_ui_generator` package (auto-split, verbatim). See crud_ui_generator/__init__.py."""
from __future__ import annotations
from ._forms import CRUD_FORM, EDIT_PAGE, NEW_PAGE
from ._pages import DETAIL_PAGE, LIST_PAGE, MANAGE_INDEX

def generate_crud_ui_files() -> dict:
    """Return the fixed, descriptor-driven CRUD UI files (relpath -> content)."""
    return {
        "src/components/CrudForm.jsx": CRUD_FORM,
        "src/app/(app)/manage/page.jsx": MANAGE_INDEX,
        "src/app/(app)/manage/[collection]/page.jsx": LIST_PAGE,
        "src/app/(app)/manage/[collection]/new/page.jsx": NEW_PAGE,
        "src/app/(app)/manage/[collection]/[id]/page.jsx": DETAIL_PAGE,
        "src/app/(app)/manage/[collection]/[id]/edit/page.jsx": EDIT_PAGE,
    }
