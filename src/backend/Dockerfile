FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# without its deps: they would pull in PyTorch, which the topics do not need (the embeddings come from OpenRouter)
RUN pip install --no-cache-dir --no-deps bertopic==0.17.4 && python -m spacy download de_core_news_lg

COPY . .

CMD python app/main.py && (python -m app.warm_thumbs &) && uvicorn app.app:app --host 0.0.0.0 --port 8000