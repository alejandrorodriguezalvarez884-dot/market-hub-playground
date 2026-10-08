# Everything is started from here, by hand. Nothing runs on a timer.
#
#   make            list the targets
#   make dev        API (port 8000) + site with reload (port 4321): run `make api` and `make dev`
#   make serve      site and API together, as in production
#   make sample     the same with made-up figures and a stand-in for the model: no network, no spend
#   make deploy     build and deploy the service to Cloud Run, behind Market Hub's sign-in

SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help install test check site api dev serve sample deploy

help: ## List the targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

install: ## Install the Python and site dependencies
	uv sync
	cd site && npm ci

test: ## Run the tests
	uv run pytest

check: test ## Tests plus the site's type check and build
	cd site && npx astro check && npm run build

site: ## Build the site into site/dist
	cd site && npm run build

api: ## Run the API alone at http://localhost:8000, with reload (pair it with `make dev`)
	PLAYGROUND_ALLOWED_ORIGINS=http://localhost:4321 uv run uvicorn playground.api:create_app --factory --reload --port 8000

dev: ## Run the site at http://localhost:4321 with reload (it calls the API on port 8000)
	cd site && PUBLIC_API_URL=http://localhost:8000 npm run dev

serve: site ## Run site and API together at http://localhost:8080 (the chat spends with the key in .env)
	PLAYGROUND_STATIC_DIR=site/dist uv run uvicorn playground.api:create_app --factory --port 8080

sample: site ## The same with made-up figures and a stand-in for the model: no network and no spend
	PLAYGROUND_SAMPLE=1 PLAYGROUND_SCRIPTED=1 HUB_URL= PLAYGROUND_STATIC_DIR=site/dist uv run uvicorn playground.api:create_app --factory --port 8080

deploy: ## Build and deploy the service to Cloud Run (see scripts/deploy-cloudrun.sh)
	./scripts/deploy-cloudrun.sh
