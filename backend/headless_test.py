import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

def run(url: str):
    out = {}
    screenshots_dir = Path(__file__).resolve().parent.parent / 'data' / 'screenshots'
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    name = 'headless-test'
    png = screenshots_dir / (name + '.png')
    html = screenshots_dir / (name + '.html')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until='networkidle', timeout=30000)
        except Exception as e:
            out['error'] = f'goto-failed: {e!s}'
            try:
                page.screenshot(path=str(png), full_page=True)
            except Exception:
                pass
            try:
                html.write_text(page.content(), encoding='utf-8')
            except Exception:
                pass
            browser.close()
            print(json.dumps(out))
            return

        # allow some time for JS-rendered content
        page.wait_for_timeout(2000)
        title = page.title()
        current = page.url
        try:
            body_text = page.evaluate('() => (document.body && document.body.innerText) || ""')
        except Exception:
            body_text = ''
        body_len = len(body_text)

        keywords = ['coupon', 'verified', 'congratulation', 'claim', 'success', 'reward', 'code']
        found = [k for k in keywords if k.lower() in body_text.lower()]

        try:
            page.screenshot(path=str(png), full_page=True)
        except Exception:
            pass
        try:
            html.write_text(page.content(), encoding='utf-8')
        except Exception:
            pass

        out.update({
            'title': title,
            'url': current,
            'body_len': body_len,
            'found_keywords': found,
            'screenshot': str(png),
            'html': str(html),
        })
        browser.close()
    print(json.dumps(out, ensure_ascii=False))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: headless_test.py <url>')
        sys.exit(2)
    run(sys.argv[1])
