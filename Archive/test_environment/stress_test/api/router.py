import json
import time
from typing import Dict, Callable, List, Optional, Tuple


class Request:
    """Simple HTTP-like request object."""

    def __init__(self, method: str, path: str, body: Optional[dict] = None, headers: Optional[dict] = None):
        self.method = method.upper()
        self.path = path
        self.body = body or {}
        self.headers = headers or {}
        self.timestamp = time.time()
from typing import Dict, List, Callable, Optional, Any
import time
import json

# Placeholder definitions
class Request:
    """Simple HTTP-like request object."""
    def __init__(self, path: str, method: str):
        self.path = path
        self.method = method

class Response:
    """Simple HTTP-like response object."""

    def __init__(self, status: int, data: dict, headers: Optional[dict] = None):
        self.status = status
        self.data = data
        self.headers = headers or {"Content-Type": "application/json"}
        self.timestamp = time.time()

    def to_json(self) -> str:
        """Serializes the response object to a JSON string."""
        response_data = {
            "status": self.status,
            "data": self.data,
            "timestamp": self.timestamp,
            "headers": self.headers
        }
        return json.dumps(response_data)

# Define the type for a handler function
Handler = Callable[[Request], Response]
Middleware = Callable[[Request, Callable[..., Any]], Any]


class Router:
    """A simple URL routing and middleware system."""
    def __init__(self):
        # Stores routes: {path: {method: handler_function}}
        self.routes: Dict[str, Dict[str, Handler]] = {}
        # Stores middleware functions
        self.middleware: List[Middleware] = []
        # Stores the fallback error handler
        self.error_handler: Optional[Handler] = None

    def add_route(self, path: str, method: str, handler: Handler):
        """Registers a handler for a specific method and path."""
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method] = handler

    def use_middleware(self, middleware_func: Middleware):
        """Registers a middleware function to run before handlers."""
        self.middleware.append(middleware_func)

    def set_error_handler(self, handler: Handler):
        """Sets a custom error handler."""
        self.error_handler = handler
    def add_route(self, method: str, path: str, handler: Callable):
        if path not in self.routes:
            self.routes[path] = {}
        self.routes[path][method.upper()] = handler

    def use_middleware(self, middleware_fn: Callable):
        self.middleware.append(middleware_fn)

    def set_error_handler(self, handler: Callable):
        # FIX: Changed 'handle' to 'handler'
        self.error_handler = handler

    def handle(self, request: Request) -> Response:
        # Middleware execution
        for mw in self.middleware:
            result = mw(request)
            if isinstance(result, Response):
                return result

        # Check 404
        if request.path not in self.routes:
            return Response(404, {"error": f"Route not found: {request.path}"})

        # Retrieve method handlers
        # FIX: Corrected typo from 'self.routs' to 'self.routes'
        method_handlers = self.routes[request.path]
        
        # Check 405
        if request.method.upper() not in method_handlers:
            return Response(405, {"error": f"Method {request.method} not allowed"})

        handler = method_handlers[request.method.upper()]
        
        # Execute handler logic
        try:
            return handler(request)
        except Exception as e:
            # Custom error handling
            if self.error_handler:
                return self.error_handler(request, e)
            return Response(500, {"error": str(e)})


class RateLimiter:
    """Simple in-memory rate limiter."""
def allow_request(self, client_id: str) -> bool:
    now = time.time()
    if client_id not in self.requests:
        self.requests[client_id] = []
    
    self.requests[client_id] = [
        t for t in self.requests[client_id] if now - t < self.window
    ]
    
    if len(self.requests[client_id]) >= self.max_requests:
        return False
        
    self.requests[client_id].append(now)
    return True
