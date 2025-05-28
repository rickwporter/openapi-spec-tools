# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

TEST_TARGET ?= tests
poetry_run ?= poetry run

default: help

###########
##@ General
all: example-gen lint cov wheel ## Complete cycle: generate/lint/test everything

# NOTE: due to example sub-projects, clean up all occurrances of these files/directories
clean: ## Remove build/test artifacts
	rm -rf `find . -name __pycache__`
	rm -rf `find . -name .pytest_cache`
	rm -rf `find . -name .ruff_cache`
	rm -rf `find . -name .coverage`
	rm -rf `find . -name htmlcov`
	rm -rf `find . -name dist`

###########
##@ Build
build: wheel
wheel: ## Build the wheel file
	poetry build

install: ## Install package(s) and development tools
	poetry install --with dev

###########
##@ Lint
lint: ## Check code formatting
	$(poetry_run) ruff check

delint: ## Fix formatting issues
	$(poetry_run) ruff check --fix

###########
##@ Test
test: ## Run unit tests (use TEST_TARGET to scope)
	$(poetry_run) pytest -v $(TEST_TARGET)

cov: ## Run unit tests with code coverage measurments (use TEST_TARGET to scope)
	$(poetry_run) coverage run -m pytest -v $(TEST_TARGET)
	$(poetry_run) coverage report -m
	$(poetry_run) coverage html

###########
##@ Examples
examples: pets-cli ct-cli gh-cli ## Complete cycle on all examples

example-gen: ## Generate example code (no tests)
	make -C examples/pets-cli gen
	make -C examples/cloudtruth-gen-cli gen
	make -C examples/github gen

pets-cli: ## Generate pets-cli
	make -C examples/pets-cli all

ct-cli: ## Generate the cloudtruth-cli
	make -C examples/cloudtruth-gen-cli all

gh-cli: ## Generate the Github CLI
	make -C examples/cloudtruth-gen-cli all
