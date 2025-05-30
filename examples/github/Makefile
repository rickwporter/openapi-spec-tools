# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


LAYOUT_FILE := layout.yaml
OPENAPI_SPEC := api.github.com.yaml
TRIMMED_SPEC := trimmed.yaml
PROJECT_DIRECTORY := .
PACKAGE_NAME := github_gen_cli

poetry_run ?= poetry run


###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: gen lint install ## Perform a full cycle
	gh-cli

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	cli-gen layout check $(LAYOUT_FILE)

trim: ## Creates the skinny OpenAPI spec
	cli-gen trim $(LAYOUT_FILE) $(OPENAPI_SPEC) --updated-file $(TRIMMED_SPEC)

gen: layout-lint ## Generate CLI code
	cli-gen generate $(LAYOUT_FILE) $(TRIMMED_SPEC) $(PACKAGE_NAME) --project-dir $(PROJECT_DIRECTORY) --no-tests

missing: ## Print the OAS operations not in the layout
	cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix
