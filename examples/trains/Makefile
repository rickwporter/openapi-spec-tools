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
PACKAGE_NAME := trains

poetry_run ?= poetry run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: install gen lint ## Perform a full cycle
	$(poetry_run) trains

###########
##@ CLI generation
gen: layout-suggest cli-regen

layout-lint:  ## Check the layout file format
	$(poetry_run) layout check $(LAYOUT_FILE)

layout-suggest: ## Create suggested layout file
	$(poetry_run) layout suggest $(OPENAPI_SPEC) $(SUGGESTED_FILE)

cli-gen: layout-lint ## Generate CLI code
	$(poetry_run) cli-gen generate $(OPENAPI_SPEC) $(PACKAGE_NAME) --layout-file $(LAYOUT_FILE) --no-tests --project-dir $(PROJECT_DIRECTORY)

cli-clean: ## Delete generated CLI code
	rm -rf $(PACKAGE_NAME)

cli-regen: cli-clean cli-gen ## Regenerate CLI code

###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix

