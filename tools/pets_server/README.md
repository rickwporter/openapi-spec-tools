# Pets server

This is an expedient implementation of the pet store API.
It is done to allow testing with a live server.
The OpenAPI specification here ne

## Creation

The implementation (in `generated/`) was initually built with `make gen`.
Following that, here's what was done:
1. Fixed the test
    * Updated `test_create_pets()` to pass a dictionary instead of a class that could not be imported -- used a negative number for the `id` to avoid any conflict.
    * Uncommented a couple tests to verify some ability to add/list.
2. Added implementation in `generated/src/openapi_server/impl/ptest.py`
    * Added rudimentary operations to manage an in memory dictionary
    * Added some sample data

The implementation is NOT robust, but allows for simple testing.
The FastAPI implemenation is multi-threaded, and the "database" operations are NOT threadsafe.

> **WARNING:** using `make rm-gen` or `make regen` will delete the implementation file and the test fix.


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
