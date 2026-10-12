#####################
# Project stuff
project_name ?= foo
package_name ?= $(project_name)
package_version ?= 0.1.0

client_dir ?= client
client_template_dir ?= templates

gen_log ?= generator.log
gen_workdir := /local
gen_currdir ?= $(shell pwd)

#####################
# Container stuff
openapi_gen_version ?= v7.11.0
openapi_gen_image ?= openapitools/openapi-generator-cli:$(openapi_gen_version)

# this allows for ovrriding with podman
DOCKER_CMD ?= docker

# automatically remove container upon completion
gen_container_args := --rm
# add user-map, so it runs as current user (not root)
gen_container_args += --user "$(shell id -u):$(shell id -g)"
# mount local directory
gen_container_args += -v $(shell pwd):$(gen_workdir)

#####################
# Client
client_spec ?= openapi.yaml
client_language ?= python

# this starts to put it all toghether -- you may need/want to do stuff here
package_async ?= false
package_unknown_enums ?= true
openapi_addition_props := packageName=$(package_name),packageVersion=$(package_version),supportAsync=$(package_async),enumUnknownDefaultCase=$(package_unknown_enums)

# specify the input source
openapi_gen_args := --input-spec $(gen_workdir)/$(client_spec)
openapi_gen_args += --generator-name $(client_language)
openapi_gen_args += --output $(gen_workdir)/$(client_dir)
openapi_gen_args += --additional-properties=$(openapi_addition_props)


#####################
# Targets
default: help

help: ## This message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

prereq: openapi-image ## Prerequisites for building the OpenAPI client

clean: ## Cleanup build artifacts
	rm -f $(openapi_gen_log)

enchilada all: client-regen ## Convenience targets
client-regen: client-rmgen client-gen ## Regenerate the client code

client-rmgen: ## Removes the previously generated client code
	rm -rf $(client_dir)

client-gen: ## Generate the client code
	$(DOCKER_CMD) run $(gen_container_args) $(openapi_gen_image) generate $(openapi_gen_args) > $(gen_log)

openapi-image: ## Pulls the openapi generator container (when needed)
ifneq ($(shell $(DOCKER_CMD) images -q $(openapi_gen_image)),)
	@echo "Already have $(openapi_gen_image)"
else
	$(DOCKER_CMD) pull $(openapi_gen_image)
endif
