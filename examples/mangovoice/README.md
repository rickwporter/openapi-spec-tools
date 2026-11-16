# Mango CLI

This CLI was developed using the OAS tools CLI generation.

## History

The Mango Voice CLI was started to demonstrate CLI generation. The initial attempt includes using a suggested `layout.yaml` generated from the `layout suggest` with configuration for pagination parameters. 

1. Copied `suggested.yaml` to `layout.yaml`
2. Renamed some of the operations to avoid duplicate names (for example, two `show` commands became a `show` and a `list` command).
3. Added `bugIds` for a few commands
    * `duplicateIds` when query parameter names conflict with body parameter names
    * `intEnumNonIntValue` when an enum is declared as a `number`, but one of the values is not a number.
4. Removed test generation due to test infrastructure issues (e.g. specifying width, exceeding size)

## Future

Some things that should be done:
* In layout file:
    * Add summary fields (e.g. `summaryFields`) for lists of complex return data
    * Specify `columns` if the display should be more controlled

## Development

This example is to demonstrate using the tools to provide a simple example of how to develop. More extensive examples will be added in other projects.
