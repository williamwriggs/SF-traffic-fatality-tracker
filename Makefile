.PHONY: install refresh app test

install:
	python -m pip install -e ".[dev]"

refresh:
	python -m src.refresh

app:
	streamlit run app.py

test:
	python -m pytest -q
