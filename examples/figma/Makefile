# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


LAYOUT_FILE := layout.yaml
SUGGESTED_FILE := suggested.yaml
OPENAPI_SPEC := openapi.yaml
PROJECT_DIRECTORY := .
PACKAGE_NAME := figma_cli

poetry_run ?= poetry run


###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: install gen lint ## Perform a full cycle
	$(poetry_run) figma --help

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	$(poetry_run) layout check $(LAYOUT_FILE)

suggest: ## Generates the suggested layout for OAS
	$(poetry_run) layout suggest $(OPENAPI_SPEC) $(SUGGESTED_FILE)

layout-update: ## Suggest using updates to the hand tailored spec
	$(poetry_run) layout suggest $(OPENAPI_SPEC) $(LAYOUT_FILE) --update

gen: layout-lint ## Generate CLI code
	$(poetry_run) cli-gen generate $(OPENAPI_SPEC) $(PACKAGE_NAME) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests

missing: ## Print the OAS operations not in the layout
	$(poetry_run) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix
