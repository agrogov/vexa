# Vexa — delegates to deploy/compose/Makefile
# Usage: make all, make up, make down, make logs, make test
.DEFAULT_GOAL := all
MAKEFLAGS += --no-print-directory

%:
	@$(MAKE) -C deploy/compose $@

.PHONY: %
