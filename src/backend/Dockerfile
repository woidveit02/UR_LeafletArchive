# the documentation from docs/ (context "repo" in docker-compose.yml), served by the app under /doku/
FROM python:3.11-slim AS docs
WORKDIR /repo
COPY --from=repo docs/requirements.txt docs/
RUN pip install --no-cache-dir -r docs/requirements.txt
COPY --from=repo mkdocs.yml .
COPY --from=repo docs docs
RUN mkdocs build --site-dir /doku

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# without its deps: they would pull in PyTorch, which the topics do not need (the embeddings come from OpenRouter)
RUN pip install --no-cache-dir --no-deps bertopic==0.17.4 && python -m spacy download de_core_news_lg

COPY . .
# outside /app, which docker-compose.yml covers with src/backend
COPY --from=docs /doku /doku

CMD python app/main.py && (python -m app.warm_thumbs &) && uvicorn app.app:app --host 0.0.0.0 --port 8000