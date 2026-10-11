# Pets server

This is an expedient implementation of the pet store API.
It is done to allow testing with a live server.
The OpenAPI specification here ne

## Creation

`make gen` (and `make regen`) runs the OpenAPI generator into `generated/`.
That directory is build output and is not committed.
After generation, the Makefile:
1. Copies `impl/pets.py` to `generated/src/openapi_server/impl/pets.py`.
    * The implementation keeps an in-memory dictionary and some sample data.
2. Applies `patches/test_pets_api.patch`.
    * `test_create_pets()` passes a dictionary instead of `openapi_server.Pet()`, which cannot be imported. The `id` is negative so it does not collide with sample data.
    * The list and create tests are uncommented.

The implementation is NOT robust, but allows for simple testing.
The FastAPI implementation is multi-threaded, and the "database" operations are NOT threadsafe.


## Running

The primary means of running the server is through the use of a Docker container.
This simplifies dependencies between `openapi-spec-tools` and the server.
The `make run` target will start the server in the foreground, so you can run the `pets-cli` example.

Here are some instructions for using the server with the `pets-cli`.
Environment setup for running the client:
```shell
cd ../../examples/pets-cli
export API_HOST=http://0.0.0.0:8080
export API_KEY=abc123
```

To see what commands are available, you can `uv run pets`. This provides help, and you can choose your journey from there.

When you are done running the server, you can hit `Ctrl-C` in the window where the server is in the foreground.
