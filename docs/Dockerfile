# Documentation site. Kept separate from the backend image on purpose: the docs
# have no reason to carry the API's dependencies, and a broken docs build must
# never be able to stop the product from starting.
FROM python:3.12-slim

WORKDIR /docs

# Copied on its own so a content change does not reinstall MkDocs.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Content is mounted at runtime by compose, so an edit is visible on save
# without rebuilding. Only the config is baked in.
COPY mkdocs.yml .

EXPOSE 8000

# --dirtyreload would be faster but skips the nav rebuild, which silently hides
# a newly added page until a full restart.
CMD ["mkdocs", "serve", "--dev-addr", "0.0.0.0:8000"]
