
from playwright.sync_api import sync_playwright

# Standard headers to look like a normal browser
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
)


def fetch_website_contents(url, max_chars=2_000):
    """
    Return the title and visible text of the website at the given url;
    truncated to max_chars (default 2,000) as a sensible limit.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle")

        title = page.title() or "No title found"

        # Strip elements we don't care about, then grab the body text.
        text = page.evaluate(
            """() => {
                document.querySelectorAll('script, style, img, input').forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }"""
        )

        browser.close()

    return (title + "\n\n" + text)[:max_chars]


def fetch_website_links(url):
    """
    Return the (absolute) links on the website at the given url.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle")

        # .href resolves relative URLs to absolute ones automatically.
        links = page.eval_on_selector_all(
            "a[href]", "elements => elements.map(el => el.href)"
        )

        browser.close()

    return [link for link in links if link]


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print("=== CONTENTS ===")
    print(fetch_website_contents(target))
    print("\n=== LINKS ===")
    for link in fetch_website_links(target):
        print(link)
