# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

OPENAPI_SPEC := ct.yaml
LAYOUT_FILE := layout.yaml
LAYOUT_START := environments
PATH_PREFIX ?= /api/v1
FLAT_PKG_NAME := cloudtruth_api.flat
PROP_PKG_NAME := cloudtruth_api.prop
OPAQUE_PKG_NAME := cloudtruth_api.opaque
FLAT_DIR := cloudtruth_api/flat
PROP_DIR := cloudtruth_api/prop
OPAQUE_DIR := cloudtruth_api/opaque

BASE_API_ARGS := --layout-file $(LAYOUT_FILE) --start $(LAYOUT_START) --prefix $(PATH_PREFIX)

poetry_run ?= poetry run

###########
##@ General
default: help

wheel: ## Build the wheel package that is installable
	poetry build

install: ## Install the package
	poetry install

all: install regen lint ## Perform a full cycle

###########
##@ Code generation
layout: ## Generate the layout file
	$(poetry_run) layout suggest $(OPENAPI_SPEC) $(LAYOUT_FILE) --prefix $(PATH_PREFIX)

gen: layout regen ## Generate all API code
regen: flat-regen prop-regen opaque-regen ## Reenerate all API code
rm-gen: flat-rm prop-rm opaque-rm ## Remove generated code

flat-regen: flat-rm flat-gen ## Regenerate API with flat arguments

flat-rm: ## Remove generated flat API
	rm -rf $(FLAT_DIR)

flat-gen: ## Generate flat API (completely unrolled properties)
	$(poetry_run) api-gen $(OPENAPI_SPEC) $(FLAT_PKG_NAME) $(BASE_API_ARGS) --body-type flat --code-dir $(FLAT_DIR)

prop-regen: prop-rm prop-gen ## Regenerate API with property level arguments

prop-rm: ## Remove generated property API
	rm -rf $(PROP_DIR)

prop-gen: ## Generate property API (first level properties visible)
	$(poetry_run) api-gen $(OPENAPI_SPEC) $(PROP_PKG_NAME) $(BASE_API_ARGS) --body-type property --code-dir $(PROP_DIR)

opaque-regen: opaque-rm opaque-gen ## Regenerate API with opaque bodies

opaque-rm: ## Remove generated opaque API
	rm -rf $(OPAQUE_DIR)

opaque-gen: ## Generate opaque API (body blobs)
	$(poetry_run) api-gen $(OPENAPI_SPEC) $(OPAQUE_PKG_NAME) $(BASE_API_ARGS) --body-type opaque --code-dir $(OPAQUE_DIR)


###########
##@ Linting
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix
