.PHONY: up down reset logs test e2e demo

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v
	rm -rf var/

logs:
	docker compose logs -f

test:
	docker compose run --rm --no-deps talent_pool sh -c "lint-imports && pytest -q"
	docker compose run --rm --no-deps push_data_manager sh -c "lint-imports && pytest -q"
	docker compose run --rm --no-deps event_logger sh -c "lint-imports && pytest -q"

e2e:
	$(MAKE) reset
	$(MAKE) up
	sleep 5
	docker compose --profile test run --rm e2e

demo:
	./demo.sh
