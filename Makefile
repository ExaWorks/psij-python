
# This allows running things like "make tests -- -k local" to pass "-k local" as args to
# pytest in the test target
ifeq (tests, $(firstword $(MAKECMDGOALS)))
  TESTARGS := $(wordlist 2, $(words $(MAKECMDGOALS)), $(MAKECMDGOALS))
  $(eval $(TESTARGS):;@true)
endif

CWD = $(shell pwd)
PYTHON = $(shell if python --version 2>&1 | egrep -q 'Python 3\..*' ; then echo "python"; else echo "python3"; fi)

.PHONY: tests
tests:
	PYTHONPATH=$(CWD)/src:$(CWD)/tests/plugins1:$(CWD)/tests/plugins2:${PYTHONPATH} \
		${PYTHON} -m pytest -v $(TESTARGS)

.PHONY: coverage-tests
coverage-tests:
	PYTHONPATH=$(CWD)/src:$(CWD)/tests/plugins1:$(CWD)/tests/plugins2:${PYTHONPATH} \
		${PYTHON} -m pytest -v --cov $(TESTARGS)
		
.PHONY: html-coverage-report
html-coverage-report:
	PYTHONPATH=$(CWD)/src:$(CWD)/tests/plugins1:$(CWD)/tests/plugins2:${PYTHONPATH} \
		${PYTHON} -m pytest -v --cov --cov-report html

.PHONY: verbose-tests
verbose-tests:
	PYTHONPATH=$(CWD)/src:$(CWD)/tests/plugins1:$(CWD)/tests/plugins2:${PYTHONPATH} \
		${PYTHON} -m pytest -v --log-format="%(asctime)s %(levelname)s %(message)s" \
			--log-date-format="%Y-%m-%d %H:%M:%S" --log-cli-level=DEBUG

.PHONY: ci-tests
ci-tests:
	${PYTHON} tests/ci_runner.py


.PHONY: typecheck
typecheck:
	mypy --config-file=.mypy --strict src tests

.PHONY: stylecheck
stylecheck:
	flake8 src tests

.PHONY: checks
checks: typecheck stylecheck docs

.PHONY: docs
docs:
	rm -rf docs/.generated
	rm -rf docs/.build
	sphinx-build --keep-going -n -W -b html docs docs/.build/


.PHONY: web-docs
web-docs:
	rm -rf docs/.generated
	rm -rf docs/.web-build
	PSIJ_WEB_DOCS=1 sphinx-multiversion docs docs/.web-build

.PHONY: style
style:
	autopep8 -i -r src tests


.PHONY: install
install:
	$(PYTHON) setup.py install

.PHONY: develop
develop:
	$(PYTHON) setup.py develop


.PHONY: tag-and-release
tag-and-release: ## create a tag in git. to run, do a 'make VERSION="version string" tag-and-release
	./tag_and_release.sh create_tag $(VERSION)
	./tag_and_release.sh package
	./tag_and_release.sh release
