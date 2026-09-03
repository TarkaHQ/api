SHELL := /bin/bash

BUF_IMAGE := bufbuild/buf:1.57.2@sha256:60dea959d4a9ea381a2c9d6f8760678845234e086f632ec01a64bb588143a226
OPENAPI_VALIDATOR_IMAGE := python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

.PHONY: all breaking generate lint test validate-agent-host-templates validate-openapi validate-product-access verify verify-docker

all: verify

lint:
	buf format --diff --exit-code
	buf lint

breaking:
	buf breaking --against '.git#branch=main'

generate:
	buf generate

validate-openapi:
	python3 scripts/validate_openapi.py

validate-product-access:
	python3 scripts/validate_product_access.py

validate-agent-host-templates:
	python3 scripts/validate_agent_host_templates.py

test:
	python3 -m unittest discover -s scripts -p 'test_*.py'

verify: lint generate validate-openapi validate-product-access validate-agent-host-templates test
	git diff --exit-code -- openapi/tarka-control-v1.swagger.json

verify-docker:
	docker run --rm --entrypoint sh -v "$(CURDIR):/workspace" -w /workspace $(BUF_IMAGE) -ec 'buf format --diff --exit-code && buf lint && buf generate'
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(OPENAPI_VALIDATOR_IMAGE) python scripts/validate_openapi.py
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(OPENAPI_VALIDATOR_IMAGE) python scripts/validate_product_access.py
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(OPENAPI_VALIDATOR_IMAGE) python scripts/validate_agent_host_templates.py
	git diff --exit-code -- openapi/tarka-control-v1.swagger.json
