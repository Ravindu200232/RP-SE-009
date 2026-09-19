"""Exercise the real toolbar with an isolated transport; no project files/model calls."""
import asyncio
import json
import re
import sys
from pathlib import Path
from playwright.async_api import async_playwright, expect

HTML = '<!DOCTYPE html><html><head><title>Editor fixture</title></head><body><h1 id="heading">Original <span id="nested">nested</span></h1><p id="copy">Initial copy</p></body></html>'
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    saved, errors = [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        async def handle(route):
            path = route.request.url.split('/__agentforge/api')[-1].split('?')[0]
            result = {}
            if path.startswith('/prototype/'):
                return await route.fulfill(content_type='text/html', body=HTML)
            if path == '/auth/me': result = {'ok':True,'user':{'id':'tester','name':'Tester'}}
            elif path == '/projects': result = [{'name':'alpha','title':'alpha','build_available':True}]
            elif path.startswith('/workflow/'): result = {'project':'alpha','build_available':True,'agents':{'designer':{'status':'completed'},'developer':{'status':'completed'}},'events':{}}
            elif path.startswith(('/open/','/runtime/')): result = {'project':'alpha','status':'stopped','revision':1,'serverId':'mock'}
            elif path == '/settings': result = {'deploy':{},'admin':False}
            elif path == '/save-file': saved.append(route.request.post_data_json); result = {'ok':True}
            await route.fulfill(content_type='application/json', body=json.dumps(result))
        await page.route('**/__agentforge/api/**', handle)
        await page.route_web_socket('**/__agentforge/ws', lambda ws: ws.on_message(lambda _: None))
        try:
            await page.goto('http://127.0.0.1:3000/__agentforge', wait_until='networkidle')
            await page.get_by_role('button',name='Projects',exact=False).first.click()
            await page.get_by_text('alpha',exact=True).first.click()
            await page.get_by_role('button',name='Prototype',exact=True).first.click()
            await page.get_by_role('button',name=re.compile('Visual Inspector')).first.click()
            frame = page.frame_locator('iframe[title="prototype-preview"]')
            await frame.locator('#heading').click()
            editor = page.get_by_role('complementary',name='HTML visual editor')
            await editor.get_by_role('textbox',name='Text content',exact=True).fill('Updated ')
            await editor.get_by_role('textbox',name='Text content',exact=True).press('Tab')
            await expect(frame.locator('#nested')).to_have_text('nested')
            await expect(frame.locator('#heading')).to_have_text('Updated nested')
            search = editor.get_by_role('textbox',name='Find customization tools')
            await search.fill('font-size')
            size = editor.get_by_role('textbox',name='font size',exact=True)
            await size.fill('40px'); await size.press('Enter')
            await expect(frame.locator('#heading')).to_have_attribute('style',re.compile('font-size: 40px'))
            await editor.get_by_role('button',name='Undo',exact=True).click()
            assert '40px' not in (await frame.locator('#heading').get_attribute('style') or '')
            await editor.get_by_role('button',name='Redo',exact=True).click()
            await editor.get_by_role('button',name='Save to HTML (Instant)',exact=True).click()
            await expect(editor.get_by_role('button',name='Saved to HTML',exact=True)).to_be_visible()
            assert len(saved) == 1 and saved[0]['project'] == 'alpha'
            assert 'font-size: 40px' in saved[0]['content'] and '__vf_selected' not in saved[0]['content']
            assert '<span id="nested">nested</span>' in saved[0]['content']
            await expect(frame.locator('#heading')).to_have_class(re.compile('__vf_selected'))
            await size.fill('32broken'); await size.press('Enter')
            await expect(editor.get_by_role('alert')).to_have_text('Invalid font-size value')
            assert not errors, errors
            print('PASS: direct text/style editing, nested markup preserved, undo/redo, HTML save without inspector artifacts, validation; no page errors')
        except Exception:
            print((await page.locator('body').inner_text())[-3500:])
            raise
        finally: await browser.close()

if __name__ == '__main__': asyncio.run(asyncio.wait_for(main(),timeout=60))
