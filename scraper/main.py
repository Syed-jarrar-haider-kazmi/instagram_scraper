import json
import sys

from .instagram_scraper import InstagramScraper


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scraper.main <instagram_username>", file=sys.stderr)
        sys.exit(1)

    username = sys.argv[1]
    scraper = InstagramScraper()

    result = scraper.scrape(username, min_posts=50)
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
