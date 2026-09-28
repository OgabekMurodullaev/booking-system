.PHONY: up down migrate test lint fmt shell seed

up:
	docker compose up -d

down:
	docker compose down

migrate:
	docker compose exec web python manage.py migrate

test:
	docker compose exec web pytest

lint:
	docker compose exec web ruff check .
	docker compose exec web ruff format --check .

fmt:
	docker compose exec web ruff format .
	docker compose exec web ruff check --fix .

shell:
	docker compose exec web python manage.py shell

seed:
	docker compose exec web python manage.py seed_demo
