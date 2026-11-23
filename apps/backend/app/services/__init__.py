"""Business logic, one module per domain. Services read/write JSON documents through `app.crud`
and log one ActivityEvent per write. Write functions take the actor `ctx` first and run in a
transaction (`@transactional`)."""
