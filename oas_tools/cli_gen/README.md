

# Layout

The layout file contains the structure for your command line interface (CLI). 

```yaml
cli:
  description: My program does this!
  operations:
  # The operations are a reference to the OAS
  - name: version
    operationId: getAppVersion
  - name: info
    operationId: getInfo
  subcommands:
  - name: resources
    subcommandId: resources_subcommand

resources_subcommand:
  description: Manage your resources
  operations:
  - name: list
    operationId: listResources
  subcommands:
  - name: containers
    subcommandId: resources_containers
  - name: memory
    subcommandId: resources_memory


resources_containers:
  description: Manager your containers
  operations:
  - name: list
    operationId: containers_list

resources_memory:
  description: Managed the cluster memory
  oprations:
  - name: by-container
    operatonId: memory_by_container
  - name: total
    operationId: memory_summary
```
