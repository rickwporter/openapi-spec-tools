# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


LAYOUT_FILE := layout.yaml
LAYOUT_CONFIG := layout_config.yaml
SUGGESTED_FILE := suggested.yaml
OPENAPI_SPEC := close.json
PROJECT_DIRECTORY := .
PACKAGE_NAME := close_cli
CODE_DIR := src/$(PACKAGE_NAME)

uv_run ?= uv run


###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	uv build

install: ## Install the package
	uv sync

all: install gen lint ## Perform a full cycle
	$(uv_run) close-cli --help

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	$(uv_run) layout check $(LAYOUT_FILE)

suggest: ## Generates the suggested layout for OAS
	$(uv_run) layout suggest $(OPENAPI_SPEC) $(SUGGESTED_FILE) --config $(LAYOUT_CONFIG)

layout-update: ## Suggest using updates to the hand tailored spec
	$(uv_run) layout suggest $(OPENAPI_SPEC) $(LAYOUT_FILE) --update

rm-gen:
	rm -rf $(CODE_DIR)

gen: layout-lint ## Generate CLI code
	$(uv_run) cli-gen generate $(OPENAPI_SPEC) --package $(PACKAGE_NAME) --code-dir $(CODE_DIR) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests

regen: rm-gen gen

missing: ## Print the OAS operations not in the layout
	$(uv_run) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

###########
##@ Linting
lint: ## Check code formatting
	$(uv_run) ruff check

delint: ## Fix formatting issues
	$(uv_run) ruff check --fix
