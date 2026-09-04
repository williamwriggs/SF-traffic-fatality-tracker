.PHONY: install refresh app test web-data web-install web-dev web-build

install:
	python -m pip install -e ".[dev]"

refresh:
	python -m src.refresh

app:
	streamlit run app.py

test:
	python -m pytest -q

web-data:
	python scripts/export_web_data.py

web-install:
	cd web && pnpm install

web-dev: web-data
	cd web && pnpm dev

web-build: web-data
	cd web && pnpm build
