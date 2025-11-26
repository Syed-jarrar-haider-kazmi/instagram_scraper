# Instagram Profile & Posts Scraper

## Overview
`instagram_scraper.py` retrieves raw profile metadata and paginated posts for any public Instagram account using pure HTTP requests. It prefers the JSON `web_profile_info` endpoint, falls back to HTML parsing, and paginates posts through Instagram's GraphQL endpoint.

## Requirements
- Python 3.10+
- Pipenv for environment management

Install dependencies:
```bash
pipenv install -r requirements.txt
```

## Configure Environment
Set your credentials before executing any scraper commands.

1. Create a `.env` file in the repo root.
2. Populate it with at least the following values (real values copied from browser requests):

```
Populate at minimum:

- `COOKIE`
- `IG_LSD`
- `IG_ASBD_ID` (defaults to `129477`)
- `IG_GRAPHQL_DOC_ID` (`32820268350897851`) # seen from live requests
- `IG_GRAPHQL_QUERY_HASH` (`8c2a529969ee035a5063f2fc8602a0fd`)
- `X_IG_APP_ID`

```
  #Use virtual enviroment
```
pipenv shell
```

## Running
Once the `.env` variables are loaded, run:
```bash
pipenv run python -m scraper.main <instagram_username>
or
pipenv run python -m scraper.main lilbieber > sample_output/lilbieber.json
```

Example:
```bash
pipenv run python -m scraper.main lilbieber
```
Outputs JSON with a `profile` section and an array of normalized `posts`.

### Optional arguments
- Adjust `min_posts` by calling `InstagramScraper().scrape(username, min_posts=200)` inside your own script.
- Instagram now expects GraphQL requests to include a `doc_id` **and** the `lsd` token captured from DevTools. Export `IG_LSD` (or `LSD`), optionally override `IG_GRAPHQL_DOC_ID` (`GRAPHQL_DOC_ID`), and keep `IG_GRAPHQL_QUERY_HASH` (`GRAPHQL_QUERY_HASH`) around as a fallback if Instagram rotates the doc again.
- Advanced: override `IG_ASBD_ID` (`ASBD_ID`) if Instagram changes the `X-ASBD-ID` header (defaults to `129477`).

## Sample Output
`sample_output/lilbieber.json` contains a captured response for reference.

## Testing
1. Run the scraper for a test handle.
2. Inspect logs / JSON to ensure at least 50 posts are returned and that required fields are populated.
