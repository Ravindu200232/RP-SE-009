from playwright.sync_api import sync_playwright
import uuid

BASE = "http://127.0.0.1:3000/__agentforge"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    def response_log(response):
        if "/srs" in response.url or response.status >= 400:
            try:
                print("RESP", response.status, response.url, response.text()[:800])
            except Exception:
                print("RESP", response.status, response.url)
    page.on("response", response_log)
    page.on("console", lambda message: print("CONSOLE", message.type, message.text))
    page.goto(BASE, wait_until="domcontentloaded")
    # Let the initial auth bootstrap settle before signup; this mirrors a real
    # user waiting for the landing page and avoids racing the auth/me request.
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Get Started").click()
    page.get_by_role("button", name="Sign up").click()
    inputs = page.locator("input")
    username = "e2e" + uuid.uuid4().hex[:8]
    email = username + "@example.test"
    for index, value in enumerate(["E2E User", username, email, "E2eTest!2026"]):
        inputs.nth(index).fill(value)
    page.get_by_role("button", name="Create account").click()
    page.wait_for_timeout(500)
    print("TOKEN_LENGTH", page.evaluate("(localStorage.getItem('agentforge_token') || '').length"))
    print("AUTH_PROJECTS", page.evaluate("() => fetch('/__agentforge/api/projects',{headers:{Authorization:'Bearer '+localStorage.getItem('agentforge_token')}}).then(async r=>({s:r.status,t:await r.text()}))"))
    page.get_by_text("SRS Generate", exact=True).click()
    page.select_option("#build-stack", "mern-microservices")
    page.locator("textarea[aria-label='Describe your app']").fill(
        "A hotel booking platform for guests and admins. Guests search available rooms by dates, book a room and pay online. Admins manage rooms, rates and bookings with KPI dashboards. Build this as a MERN microservices application."
    )
    page.get_by_role("button", name="Generate SRS").click()
    page.wait_for_timeout(3000)
    print("URL", page.url)
    print(page.locator("body").inner_text()[:6000])
    print("TEXTAREAS", page.locator("textarea").count())
    print("BUTTONS", page.locator("button").all_inner_texts()[-50:])
    browser.close()
