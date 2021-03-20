
CWD = $(shell pwd)
PYTHON = $(shell if python --version 2>&1 | egrep -q 'Python 3\..*' ; then echo "python"; else echo "python3"; fi)

.PHONY: tests
tests:
	PYTHONPATH=$(CWD)/src ${PYTHON} -m pytest


.PHONY: typecheck
typecheck:
	mypy --config-file=.mypy --strict src tests

.PHONY: stylecheck
stylecheck:
	flake8 src
	flake8 tests

.PHONY: checks
check: typecheck stylecheck


.PHONY: genautodocs
genautodocs: 
	rm -rf docs/.generated
	mkdir docs/.generated
	sphinx-apidoc -f -o docs/.generated src/
	

.PHONY: docs
docs: genautodocs docs-noauto


.PHONY: docs-noauto
docs-noauto:
	sphinx-build -W -b html docs docs/.build/