default: build

COMPOSE_FILE_DEV = docker-compose-dev.yml

IMAGE_NAME=bireme/iahx-controller
#export APP_VER?=$(shell git describe --tags --long --always | sed 's/-g[a-z0-9]\{7\}//' | sed 's/-/\./')
export APP_VER?="2.0"
TAG_LATEST=$(IMAGE_NAME):latest

## variable used in docker-compose for tag the build image
export IMAGE_TAG=$(IMAGE_NAME):$(APP_VER)

tag:
	@echo "IMAGE TAG:" $(IMAGE_TAG)

## dev shortcuts
dev_build:
	@docker compose -f $(COMPOSE_FILE_DEV) build

dev_build_no_cache:
	@docker compose -f $(COMPOSE_FILE_DEV) build --no-cache

dev_run:
	@docker compose -f $(COMPOSE_FILE_DEV) up

dev_start:
	@docker compose -f $(COMPOSE_FILE_DEV) up -d

dev_rm:
	@docker compose -f $(COMPOSE_FILE_DEV) rm -f

dev_logs:
	@docker compose -f $(COMPOSE_FILE_DEV) logs -f

dev_stop:
	@docker compose -f $(COMPOSE_FILE_DEV) stop

dev_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) exec iahx_controller bash

dev_cache_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) exec iahx_controller_cache bash

dev_import_decs_redis:
	python controller/util/import_decs_redis.py
