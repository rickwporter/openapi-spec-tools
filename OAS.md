# oas

This tool provides some OpenAPI spec analysis and modification functionality.

Much of the work is done in the `utils.py`, while the `oas.py` provides a CLI wrapper over many of the functions. The intention is to allow the `utils.py` to grow with functionality that can be readily imported without using the CLI. 

This section highlights some of the reasons for these tools.

Here are some top-level function:
* `info` - prints the info section of the OAS where project information is provided
* `summary` - provides statistcs about an OAS just to give an idea of scope.
* `diff` - provides a YAML-centric means of looking at differences in OAS terms.
* `analyze` - provides OAS analysis tools (more in section below)
* `update` - provides some "common" modifications to perform on an OAS

Some of the above topics are explored in more depth below.

## diff

The diff provides a more YAML-centric means of looking at the data. Instead of the output of the tradition diff utility, this provides the whole structure for things that have changed. Here's an example:
```shell
(.env) ~/oas-tools> oas diff old_ct.yaml ct.yaml 
components:
    schemas:
        AwsPullTaskStep:
            required: removed url
        AwsPush:
            properties:
                name:
                    maxLength: 256 != 512
        AwsPushTask:
            required: added state
paths:
    /api/schema/:
        get:
            parameters[1]:
                schema:
                    enum: removed bs
    /api/v1/audit/:
        get:
            parameters[2]:
                description: Returns recor... != Returns the r...
    /api/v1/groups/:
        post:
            requestBody:
                content:
                    multipart/form-data: removed

(.env) ~/oas-tools> 
```

Unlike the [openapi-diff tool](https://github.com/OpenAPITools/openapi-diff), this program does NOT make any judgements about what is a breaking change or not.


## analyze

The analyze tools are a collection of small utilities to provide information about an OpenAPI specification. This portion of the tooling was born from the recurring question of, "If I modify X, what will be impacted?"

Here's a sample of the things that can be done:
* `oas analyze ops list` - list all the operations in the OAS, with ability to search
* `oas analyze ops show <op-name>` - show the schema for a specific operation
* `oas analyze ops models <op-name>` - list all the models referenced by a specific operation
* `oas analyze path list` - list all the path, with abiltity to search
* `oas analyze tags show <tag-name>` - list all the operations with the specified tag

The `oas analyze --help` is the best means to keep up with the commands, since documentation is notorious for getting outdated.


## update

The update tool has several options which have been crucial at different companies. The general idea is that it is often easier to create a modified OAS than it is to fix issues with templates.

The `--updated-filename` is a means of creating an output file. The program does NOT (by default) modify the existing OAS, so you can compare changes to the input to changes to the output.

The `--display` option controls what is displayed to the screen. Depending on the size of the changes, it may be desirable to see more or less info. 

The remainder of this section is dedicated to describing the different modification options.

### Nullable Not Required

In some versions of the OpenAPI Python generator, you will get errors when the value is `null`. To avoid this problem, it is easiest to remove the nullable properties from the required list of the object using `--nullable-not-required`.

### Remove All Tags

Tags are a great way of organizing your API. However, there are sometimes cases were you only need to perform a couple operations and they fall under different tags. To avoid having to create multiple API clients (which are based on tags) to deal with this, you can remove all the tags using `--remove-all-tags`. This puts all the operations in the same default client.

### Removed/Allow Operations

The `--remove-op` or `--allow-op` can be used to provide a list of operations to be removed or passed through. There are a couple reasons for filtering the operations in an OpenAPI spec:
* Generate less, unused code
* Avoid code generation issues with certain operations

It is pretty common to commit generated client code for many reasons. When building a whole CICD pipeline, you may not have the ability to generate code in all stages (e.g. static code analysis, security scans). It also makes it easier for editors to help with auto-completion when the code is available. 

However, if you generating code for unused operations causes unnecessary churn in the code that provides little value.

All this said, the allow/remove operations provide a means to trim your OpenAPI specification to be targetted for your specific need. When operations are removed, all the models that a no longer needed are also removed.
