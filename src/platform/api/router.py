"""
URL router with path parameter extraction and method dispatch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class RequestContext:
    """Incoming request abstraction."""
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    subject: Optional[Any] = None  # Populated by RBACMiddleware


@dataclass
class ResponseContext:
    """Outgoing response abstraction."""
    status_code: int = 200
    body: Optional[Dict[str, Any]] = None
    headers: Dict[str, str] = field(default_factory=dict)


Handler = Callable[[RequestContext], ResponseContext]


@dataclass
class Route:
    """A registered route with pattern, method, and handler."""
    pattern: str
    method: str
    handler: Handler
    _regex: re.Pattern = field(init=False, repr=False)
    _param_names: List[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._param_names = re.findall(r"\{(\w+)\}", self.pattern)
        regex_str = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", self.pattern)
        self._regex = re.compile(f"^{regex_str}$")

    def match(self, path: str) -> Optional[Dict[str, str]]:
        m = self._regex.match(path)
        if m:
            return m.groupdict()
        return None


class APIRouter:
    """URL router supporting path parameters and HTTP method dispatch."""

    def __init__(self) -> None:
        self._routes: List[Route] = []

    def add_route(self, pattern: str, method: str, handler: Handler) -> None:
        self._routes.append(Route(pattern=pattern, method=method.upper(), handler=handler))

    def get(self, pattern: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self.add_route(pattern, "GET", fn)
            return fn
        return decorator

    def post(self, pattern: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self.add_route(pattern, "POST", fn)
            return fn
        return decorator

    def put(self, pattern: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self.add_route(pattern, "PUT", fn)
            return fn
        return decorator

    def delete(self, pattern: str) -> Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            self.add_route(pattern, "DELETE", fn)
            return fn
        return decorator

    def dispatch(self, request: RequestContext) -> ResponseContext:
        matched_routes: List[Tuple[Route, Dict[str, str]]] = []
        for route in self._routes:
            params = route.match(request.path)
            if params is not None:
                matched_routes.append((route, params))

        if not matched_routes:
            return ResponseContext(status_code=404, body={"error": "Not found"})

        for route, params in matched_routes:
            if route.method == request.method.upper():
                request.path_params = params
                return route.handler(request)

        return ResponseContext(status_code=405, body={"error": "Method not allowed"})
