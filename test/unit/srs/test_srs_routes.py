"""The router's POST routes must take their bodies as bodies.

`routers/srs.py` begins with `from __future__ import annotations`, so every
annotation is a string and nothing is resolved at import time. A request model
that is deleted, renamed or never defined therefore does not raise: FastAPI
cannot resolve the name, decides the parameter must be a query string, and the
route answers 422 "Field required, loc: [query, request]" to every caller.

That is exactly how `/wireframes/html` broke - the model was removed with some
neighbouring code, the module imported cleanly, the tests passed, and the
failure only appeared as "[object Object]" in the studio. This test is the
check that import could not perform.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "srs-agent"))

from fastapi.routing import APIRoute  # noqa: E402

from srs_agent.app.routers.srs import router  # noqa: E402


def _posts():
    for route in router.routes:
        if isinstance(route, APIRoute) and "POST" in route.methods:
            yield route


def test_every_post_route_is_registered():
    assert list(_posts()), "the SRS router declares no POST routes at all"


@pytest.mark.parametrize("route", list(_posts()), ids=lambda r: r.path)
def test_a_post_body_is_never_read_as_a_query_string(route):
    """A parameter named `request` must be a body, not a query parameter."""
    queries = [f.name for f in route.dependant.query_params]
    assert "request" not in queries, (
        f"{route.path} takes `request` as a query parameter, which means its "
        "model could not be resolved - check that the class still exists above "
        "the route."
    )


@pytest.mark.parametrize("route", list(_posts()), ids=lambda r: r.path)
def test_a_route_that_names_a_model_actually_got_one(route):
    """`request: SomeModel` must have produced a body field."""
    annotated = "request" in route.endpoint.__annotations__
    if not annotated:
        pytest.skip(f"{route.path} takes no request model")
    assert route.dependant.body_params, (
        f"{route.path} annotates a request model but FastAPI found no body "
        "field for it"
    )
