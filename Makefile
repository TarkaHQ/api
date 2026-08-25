SHELL := /bin/bash

BUF_VERSION := 1.57.2
OPENAPI_VALIDATOR_IMAGE := python:3.13-slim

.PHONY: all breaking generate lint validate-openapi verify verify-docker

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

verify: lint generate validate-openapi
	git diff --exit-code -- openapi/tarka-control-v1.swagger.json

verify-docker:
	docker run --rm --entrypoint sh -v "$(CURDIR):/workspace" -w /workspace bufbuild/buf:$(BUF_VERSION) -ec 'buf format --diff --exit-code && buf lint && buf generate'
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(OPENAPI_VALIDATOR_IMAGE) python scripts/validate_openapi.py
	git diff --exit-code -- openapi/tarka-control-v1.swagger.json
