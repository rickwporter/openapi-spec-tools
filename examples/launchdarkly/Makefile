# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

LAYOUT_FILE := layout.yaml
LAYOUT_CONFIG := layout_config.yaml
SUGGESTED_FILE := suggested.yaml
OPENAPI_SPEC := ld-openapi.json
PROJECT_DIRECTORY := .
PACKAGE_NAME := launchdarkly_cli

UV_RUN ?= uv run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	uv build

install: ## Install the package
	uv sync

all: install gen lint ## Perform a full cycle
	$(UV_RUN) ld-cli --help

###########
##@ CLI generation
gen: layout-suggest cli-regen

layout-lint:  ## Check the layout file format
	$(UV_RUN) layout check $(LAYOUT_FILE)

layout-suggest: ## Create suggested layout file
	$(UV_RUN) layout suggest $(OPENAPI_SPEC) $(SUGGESTED_FILE) --config $(LAYOUT_CONFIG)

cli-gen: layout-lint ## Generate CLI code
	$(UV_RUN) cli-gen generate $(OPENAPI_SPEC) --package $(PACKAGE_NAME) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests

missing: ## Print the OAS operations not in the layout
	$(UV_RUN) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

cli-clean: ## Delete generated CLI code
	rm -rf $(PACKAGE_NAME)

cli-regen: cli-clean cli-gen ## Regenerate CLI code

###########
##@ Linting
lint: ## Check code formatting
	$(UV_RUN) ruff check

delint: ## Fix formatting issues
	$(UV_RUN) ruff check --fix
