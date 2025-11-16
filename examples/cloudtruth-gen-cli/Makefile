# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

LAYOUT_FILE := layout.yaml
SUGGESTED_FILE := suggested.yaml
UPDATED_FILE := updated.yaml
OPENAPI_SPEC := ct.yaml
PROJECT_DIRECTORY := .
PACKAGE_NAME := cloudtruth_gen_cli
PATH_PREFIX := /api/v1

TEST_TARGET ?= tests
poetry_run ?= poetry run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: install gen lint ## Perform a full cycle
	$(poetry_run) cloudtruth 

###########
##@ Code generation
layout-lint:  ## Check the layout file format
	$(poetry_run) layout check $(LAYOUT_FILE)

gen: layout-lint suggest update ## Generate CLI code
	$(poetry_run) cli-gen generate $(OPENAPI_SPEC) $(PACKAGE_NAME) --layout-file $(LAYOUT_FILE) --project-dir $(PROJECT_DIRECTORY) --no-tests

missing: ## Print the OAS operations not in the layout
	$(poetry_run) cli-gen unreferenced $(LAYOUT_FILE) $(OPENAPI_SPEC)

suggest: ## Use the local code to suggest a layout
	$(poetry_run) ./layout.py $(OPENAPI_SPEC) $(SUGGESTED_FILE) --prefix $(PATH_PREFIX)

update: ## Generates a new layout using the old as a guide
	$(poetry_run) cli-gen update $(LAYOUT_FILE) $(OPENAPI_SPEC) --new-file $(UPDATED_FILE) --prefix $(PATH_PREFIX) --indent 2

###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix


###########
##@ Test
test: ## Run unit tests
	$(poetry_run) pytest -v $(TEST_TARGET)

cov: ## Run unit tests with code coverage measurments
	$(poetry_run) coverage run -m pytest -v $(TEST_TARGET)
	$(poetry_run) coverage report -m
	$(poetry_run) coverage html
