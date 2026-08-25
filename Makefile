SHELL := /bin/bash

BUF_VERSION := 1.57.2
GO_IMAGE := golang:1.25-bookworm

.PHONY: all breaking generate lint test verify verify-docker

all: verify

lint:
	buf format --diff --exit-code
	buf lint

breaking:
	buf breaking --against '.git#branch=main'

generate:
	buf generate

test:
	go test ./...

verify: lint generate test
	git diff --exit-code -- gen openapi

verify-docker:
	docker run --rm --entrypoint sh -v "$(CURDIR):/workspace" -w /workspace bufbuild/buf:$(BUF_VERSION) -ec 'buf format --diff --exit-code && buf lint && buf generate'
	docker run --rm -v "$(CURDIR):/workspace" -w /workspace $(GO_IMAGE) go test ./...
	git diff --exit-code -- gen openapi
