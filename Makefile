# the first target is the default, so just run help
help: ## This message
	@echo "===================="
	@echo " Available Commands"
	@echo "===================="
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

TEST_TARGET ?= tests
poetry_run ?= poetry run
EXAMPLE_DIRS := examples/pets-cli
EXAMPLE_DIRS += examples/cloudtruth-gen-cli
EXAMPLE_DIRS += examples/github

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

poetry-update: ## Update poetry in top-level, and then all examples (part of release)
	poetry update
	@for dname in $(EXAMPLE_DIRS); do \
		echo "Entering $${dname}" && cd $${dname} && poetry update && cd - > /dev/null || exit 1; \
	done

###########
##@ Build
build: wheel
wheel: ## Build the wheel file
	poetry build

prereq: install
install: ## Install package(s) and development tools
	poetry install --with dev

uncommitted: ## Check for uncommitted changes
	make -f uncommitted.mk check

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
example: ## Complete cycle on all examples
	@for dname in $(EXAMPLE_DIRS); do \
		echo "Entering $${dname}" && make -C $${dname} all || exit 1; \
	done

example-gen: ## Generate example code (no tests)
	@for dname in $(EXAMPLE_DIRS); do \
		echo "Entering $${dname}" && make -C $${dname} gen || exit 1; \
	done
