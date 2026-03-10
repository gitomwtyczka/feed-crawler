"""Szybka weryfikacja nowych feedów ekonomicznych."""
import asyncio
import httpx
import yaml

async def verify():
    with open("config/sources.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Check only feeds with economic departments
    eco_feeds = [s for s in config["sources"] if any(d in s.get("departments", []) for d in ["ekonomia", "statystyki"])]
    print(f"Feedów ekonomicznych: {len(eco_feeds)}")

    ok, fail = [], []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for feed in eco_feeds:
            url = feed.get("rss_url", "")
            if not url:
                continue
            try:
                r = await client.get(url, headers={"User-Agent": "FeedCrawler/1.0"})
                if r.status_code < 400:
                    ok.append(feed["name"])
                    print(f"  OK  {r.status_code} {feed['name']}")
                else:
                    fail.append((feed["name"], f"HTTP {r.status_code}"))
                    print(f"  FAIL {r.status_code} {feed['name']}")
            except Exception as e:
                fail.append((feed["name"], str(e)[:60]))
                print(f"  ERR  {feed['name']}: {str(e)[:60]}")

    print(f"\nOK: {len(ok)}, FAIL: {len(fail)}")
    if fail:
        print("\nMartwych:")
        for name, err in fail:
            print(f"  - {name}: {err}")
    return fail

if __name__ == "__main__":
    asyncio.run(verify())
