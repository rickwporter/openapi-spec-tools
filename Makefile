# the first target is the default, so just run help
help: ## This message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


TEST_TARGET ?= tests
poetry_run ?= poetry run

default: help

lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix

test: ## Run unit tests (use TEST_TARGET to scope)
	$(poetry_run) pytest -v $(TEST_TARGET)

cov: ## Run unit tests with code coverage measurments (use TEST_TARGET to scope)
	$(poetry_run) coverage run -m pytest -v $(TEST_TARGET)
	$(poetry_run) coverage report -m
	$(poetry_run) coverage html

###########
##@ Examples
examples: pets-cli ## Generate all examples

pets-cli: ## Generate pets-cli
	make -C examples/pets-cli gen
