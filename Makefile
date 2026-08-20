.PHONY: clean tests test build


clean:
	docker compose -f tests/compose.yaml down --remove-orphans --volumes
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .venv -o -name pypostgres.egg-info \) -exec rm -rf {} +
	rm -rf tests/psycopg2

tests:
	docker compose -f tests/compose.yaml up --wait --detach
	export PGUSER=postgres
	export PGPASSWORD=postgres
	uv sync
	uv pip install -e .[dev]
	
	# Run the native psycopg2 test suite
	# https://github.com/psycopg/psycopg2/tree/master/tests
# 	[ ! -d "tests/psycopg2" ] && mkdir tests/psycopg2 && git clone --depth 1 --filter=blob:none --sparse https://github.com/psycopg/psycopg2.git tests/psycopg2 && git -C tests/psycopg2 sparse-checkout set tests


	LOGLEVEL=DEBUG uv run pytest -rP --log-cli-level=DEBUG --capture=no
	docker compose -f tests/compose.yaml down --remove-orphans --volumes

test: tests


build:
	uv build
