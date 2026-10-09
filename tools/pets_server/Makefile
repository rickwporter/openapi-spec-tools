#####################
# Project stuff
gen_dir ?= generated

gen_log ?= generator.log
gen_workdir := /local
gen_currdir ?= $(shell pwd)

#####################
# Container stuff
openapi_gen_version ?= v7.26.0
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
# Server
oas ?= openapi.yaml
language ?= python-fastapi

# specify the input source
openapi_gen_args := --input-spec $(gen_workdir)/$(oas)
openapi_gen_args += --generator-name $(language)
openapi_gen_args += --output $(gen_workdir)/$(gen_dir)


#####################
# Targets
default: help

help: ## This message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

prereq: openapi-image ## Prerequisites for building the OpenAPI server

clean: ## Cleanup build artifacts
	rm -f $(openapi_gen_log)

enchilada all: regen ## Convenience targets
regen: rmgen gen ## Regenerate the server code

rmgen: ## Removes the previously generated server code
	rm -rf $(gen_dir)

gen: ## Generate the client code
	$(DOCKER_CMD) run $(gen_container_args) $(openapi_gen_image) generate $(openapi_gen_args) > $(gen_log)

openapi-image: ## Pulls the openapi generator container (when needed)
ifneq ($(shell $(DOCKER_CMD) images -q $(openapi_gen_image)),)
	@echo "Already have $(openapi_gen_image)"
else
	$(DOCKER_CMD) pull $(openapi_gen_image)
endif
