"""HTTP layer: one thin APIRouter per resource. Routers parse the request (query params, body
schema, actor header) and call a service; business logic lives in app/services."""
