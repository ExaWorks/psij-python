
CWD = $(shell pwd)
PYTHON = $(shell if python --version 2>&1 | egrep -q 'Python 3\..*' ; then echo "python"; else echo "python3"; fi)

.PHONY: tests
tests:
	PYTHONPATH=$(CWD)/src:${PYTHONPATH} ${PYTHON} -m pytest -v

.PHONY: verbose-tests
verbose-tests:
	PYTHONPATH=$(CWD)/src:${PYTHONPATH} ${PYTHON} -m pytest -v --log-format="%(asctime)s %(levelname)s %(message)s" \
		           --log-date-format="%Y-%m-%d %H:%M:%S" --log-cli-level=DEBUG


.PHONY: typecheck
typecheck:
	mypy --config-file=.mypy --strict src tests

.PHONY: stylecheck
stylecheck:
	flake8 src
	flake8 tests

.PHONY: checks
checks: typecheck stylecheck

.PHONY: docs
docs:
	rm -rf docs/.generated
	sphinx-build -W -b html docs docs/.build/

.PHONY: style
style:
	autopep8 -i -r src tests


.PHONY: launcher-scripts
launcher-scripts:
	$(PYTHON) setup.py launcher_scripts

.PHONY: install
install:
	$(PYTHON) setup.py install

.PHONY: develop
develop:
	$(PYTHON) setup.py develop
