# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

LAYOUT_FILE := layout.yaml
SUGGESTED_FILE := suggested.yaml
UPDATED_FILE := updated.yaml
GEN_CONFIG := gen_config.yaml
LAYOUT_CONFIG := layout_config.yaml
OPENAPI_SPEC := ct.yaml
PACKAGE_NAME := cloudtruth_gen_cli
PROJECT_DIRECTORY := .
PATH_PREFIX := /api/v1

TEST_TARGET ?= tests
uv_run ?= uv run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	uv build

install: ## Install the package
	uv sync

all: install gen lint ## Perform a full cycle
	$(uv_run) cloudtruth --help

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	$(uv_run) layout check $(LAYOUT_FILE)

gen: layout-lint suggest update ## Generate CLI code
	$(uv_run) cli-gen generate $(OPENAPI_SPEC) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests --config $(GEN_CONFIG)

missing: ## Print the OAS operations not in the layout
	$(uv_run) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

suggest: ## Use the local code to suggest a layout
	$(uv_run) layout suggest $(OPENAPI_SPEC) $(SUGGESTED_FILE) --prefix $(PATH_PREFIX) --config $(LAYOUT_CONFIG)

update: ## Generates a new layout using the old as a guide
	$(uv_run) cli-gen update $(LAYOUT_FILE) $(OPENAPI_SPEC) --new-file $(UPDATED_FILE) --prefix $(PATH_PREFIX) --indent 2

rm-gen: ## Delete generated CLI code
	rm -rf $(PACKAGE_NAME)

regen: rm-gen gen ## Delete and generate CLI code

###########
##@ Linting
lint: ## Check code formatting
	$(uv_run) ruff check

delint: ## Fix formatting issues
	$(uv_run) ruff check --fix


###########
##@ Test
test: ## Run unit tests
	$(uv_run) pytest -v $(TEST_TARGET)

cov: ## Run unit tests with code coverage measurments
	$(uv_run) coverage run -m pytest -v $(TEST_TARGET)
	$(uv_run) coverage report -m
	$(uv_run) coverage html
