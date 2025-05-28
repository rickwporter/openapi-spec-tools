# NOTES: 
#   * variables initialized when the Makefile is loaded, so do this in a separate file
#   * STATUS appears to go unused, but is sometimes required to update git
STATUS := $(shell git status)
CHANGED = $(shell git ls-files --modified --deleted --other --exclude-standard)

check: ##
ifeq ($(CHANGED),)
	@echo "No changed files"
else
	$(error Found changes in: $(CHANGED))
endif
