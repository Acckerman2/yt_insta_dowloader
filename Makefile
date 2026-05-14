.PHONY: install run docker-build docker-run clean lint

install:
	uv pip install --system -r requirements.txt

run:
	python app/main.py

docker-build:
	docker compose build

docker-run:
	docker compose up -d

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf downloads/* logs/*

lint:
	ruff check app/ --fix
	ruff format app/

shell:
	python -c "from app.bot import bot, dp; from app.database import db; print('Bot shell ready')"
