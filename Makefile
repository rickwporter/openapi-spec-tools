# the first target is the default, so just run help
help: ## This message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


poetry_run ?= poetry run

default: help

lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix

test: ## Run unit tests
	$(poetry_run) pytest -v

cov: ## Run unit tests with code coverage measurments
	$(poetry_run) coverage run -m pytest -v
	$(poetry_run) coverage report -m
	$(poetry_run) coverage html
