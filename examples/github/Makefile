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

uv_run ?= uv run


###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	uv build

install: ## Install the package
	uv sync

all: install gen lint ## Perform a full cycle
	$(uv_run) gh-cli --help

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	$(uv_run) layout check $(LAYOUT_FILE)

trim: ## Creates the skinny OpenAPI spec
	$(uv_run) cli-gen trim $(LAYOUT_FILE) $(OPENAPI_SPEC) --updated-file $(TRIMMED_SPEC) --remove examples

gen: layout-lint trim ## Generate CLI code
	$(uv_run) cli-gen generate $(TRIMMED_SPEC) $(PACKAGE_NAME) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests

missing: ## Print the OAS operations not in the layout
	$(uv_run) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

###########
##@ Linting
lint: ## Check code formatting
	$(uv_run) ruff check

delint: ## Fix formatting issues
	$(uv_run) ruff check --fix
