"""Browser regression for role-specific history and explicit Build Now navigation.

Run against a Studio build with STUDIO_TEST_URL (defaults to localhost:3157).
The transport is mocked; this test does not invoke models or alter real projects.
"""
import asyncio
import json
import os
import time
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from playwright.async_api import async_playwright, expect


async def main():
    ready = {"alpha": True, "beta": False}
    sent = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def handle(route):
            path = route.request.url.split('/__agentforge/api')[-1].split('?')[0]
            result = {}
            if path == '/auth/me':
                result = {"ok": True, "user": {"id": "tester", "name": "Tester", "username": "tester", "email": "test@example.test"}}
            elif path == '/projects':
                result = [{"name": name, "title": name, "prototype_only": True, "spec_only": False,
                           "build_available": allowed} for name, allowed in ready.items()]
            elif path.startswith('/workflow/'):
                name = path.rsplit('/', 1)[1]
                result = {"project": name, "updated_at": time.time(), "build_available": ready[name],
                    "agents": {"designer": {"status": "completed" if ready[name] else "running"}, "developer": {"status": "idle"}},
                    "events": {"designer": [{"type": "agent_msg", "text": f"{name} design memory", "at": 1}],
                               "developer": [{"type": "agent_msg", "text": f"{name} build memory", "at": 1}]}}
            elif path.startswith(('/open/', '/runtime/')):
                result = {"project": path.split('/')[2], "status": "stopped", "revision": 1, "serverId": "mock"}
            elif path.startswith('/prototype/'):
                return await route.fulfill(content_type='text/html', body='<html><head></head><body><h1>Prototype</h1><button>Example</button></body></html>')
            elif path.startswith('/files/'):
                result = {'app/page.jsx': {'content': 'export default ()=>null'}}
            elif path == '/models':
                result = {'local': [], 'cloud': []}
            elif path.startswith('/qa/'):
                result = {'project': path.rsplit('/', 1)[1], 'stages': {}}
            await route.fulfill(content_type='application/json', body=json.dumps(result))

        await page.route('**/__agentforge/api/**', handle)
        await page.route_web_socket('**/__agentforge/ws', lambda ws: ws.on_message(lambda message: sent.append(json.loads(message))))
        await page.goto(os.environ.get('STUDIO_TEST_URL', 'http://127.0.0.1:3157/__agentforge'), wait_until='networkidle')
        try:
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('alpha', exact=True).first.click()
            await expect(page.get_by_text('alpha design memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('alpha build memory', exact=True)).to_have_count(0)
            await page.get_by_role('button', name='Preview', exact=True).click()
            await expect(page.get_by_text('alpha build memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('alpha design memory', exact=True)).to_have_count(0)
            await page.get_by_role('button', name='Prototype', exact=True).click()
            await expect(page.get_by_text('alpha design memory', exact=True)).to_be_visible()
            await expect(page.get_by_role('button', name='All', exact=True)).to_have_count(0)
            composer = page.locator('aside textarea')
            await composer.fill('Designer draft')
            await page.frame_locator('iframe[title="prototype-preview"]').locator('body').evaluate("() => console.error('Designer-only error')")
            await page.get_by_role('button', name='Preview', exact=True).click()
            await expect(composer).to_have_value('')
            await composer.fill('Developer draft')
            await composer.press('Enter')
            await expect(composer).to_have_value('')
            assert 'Designer-only error' not in sent[-1].get('console', ''), sent[-1]
            await page.evaluate("window.__studioFeed({type:'done',project:'alpha',agent:'developer',at:Date.now()})")
            await page.get_by_role('button', name='Prototype', exact=True).click()
            await expect(composer).to_have_value('Designer draft')
            await composer.press('Enter')
            await expect(composer).to_have_value('')
            assert 'Designer-only error' in sent[-1].get('console', ''), sent[-1]
            await page.evaluate("window.__studioFeed({type:'done',project:'alpha',agent:'designer',at:Date.now()})")
            await page.get_by_role('button', name='Preview', exact=True).click()
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('beta', exact=True).first.click()
            await expect(page.get_by_text('beta design memory', exact=True)).to_be_visible()
            await expect(page.get_by_role('button', name='Preview', exact=True)).to_be_disabled()
            await expect(page.get_by_text('alpha design memory', exact=True)).to_have_count(0)
            # Background alpha output cannot appear in beta's current conversation.
            await page.evaluate("window.__studioFeed({type:'agent_msg',project:'alpha',agent:'developer',text:'alpha background update',at:Date.now()})")
            await expect(page.get_by_text('alpha background update', exact=True)).to_have_count(0)
            ready['beta'] = True
            await page.evaluate("window.__studioFeed({type:'done',project:'beta',agent:'designer',at:Date.now()})")
            await expect(page.get_by_text('beta design memory', exact=True)).to_be_visible()
            await expect(page.get_by_role('button', name='Build App Now', exact=True).first).to_be_enabled()
            await page.get_by_role('button', name='Build App Now', exact=True).first.click()
            await expect(page.get_by_text('beta build memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('beta design memory', exact=True)).to_have_count(0)
            assert any(message.get('type') == 'agent_resume' and message.get('agent') == 'developer' and message.get('project') == 'beta' for message in sent), sent
            # Synchronization cannot change the currently visible conversation.
            await page.evaluate("window.__studioFeed({type:'agent_msg',project:'beta',agent:'designer',text:'Prototype mirror complete',at:Date.now()}); window.__studioFeed({type:'sync_state',project:'beta',status:'completed',version:'1.1.0'})")
            await expect(page.get_by_text('beta build memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('Prototype mirror complete', exact=True)).to_have_count(0)
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('alpha', exact=True).first.click()
            await expect(page.get_by_text('alpha build memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('alpha background update', exact=True)).to_be_visible()
            # Reload restores this project's last preview and its own saved history.
            await page.reload(wait_until='networkidle')
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('alpha', exact=True).first.click()
            await expect(page.get_by_text('alpha build memory', exact=True)).to_be_visible()
            await expect(page.get_by_text('alpha design memory', exact=True)).to_have_count(0)
            assert not errors, errors
            print('PASS: isolated histories, drafts and console evidence; project switching and reload; background sync; prototype gate; explicit Build Now')
        except Exception:
            await page.screenshot(path=str(Path(__file__).parent / 'results/workflow-browser-failure.png'), full_page=True)
            print((await page.locator('body').inner_text())[:3500])
            raise
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
