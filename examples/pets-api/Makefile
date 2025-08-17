# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

OPENAPI_SPEC := pet.yaml
PACKAGE_NAME := pets_api

poetry_run ?= poetry run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: install gen lint ## Perform a full cycle

###########
##@ API generation
gen: api-regen ## Regenerate API code
api-regen: rm-gen api-gen ## Regenerate the API code

api-gen: ## Generate ALI code
	$(poetry_run) api-gen $(OPENAPI_SPEC) $(PACKAGE_NAME)

rm-gen: ## Remove generated code
	rm -rf $(PACKAGE_NAME)

###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix
