"""Deployment UI with mocked transport; never calls a cloud provider or model."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from playwright.async_api import async_playwright, expect

sys.stdout.reconfigure(encoding='utf-8')


async def main():
    aws_profile = 'af-tester-agentforge-console'
    credentials = {'github_token_set': True, 'netlify_token_set': True, 'azure_credentials_set': True,
                   'aws_profile': 'af-tester-old', 'aws_region': 'ap-south-1'}
    calls, jobs, errors = [], {}, []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 1100})
        page.on('pageerror', lambda error: errors.append(str(error)))
        async def handle(route):
            path = route.request.url.split('/__agentforge/api')[-1].split('?')[0]
            result = {}
            if path == '/auth/me':
                result = {'ok': True, 'user': {'id': 'tester', 'name': 'Tester'}}
            elif path == '/projects':
                result = [{'name': name, 'title': name, 'build_available': True} for name in ['alpha', 'beta']]
            elif path.startswith('/workflow/'):
                result = {'project': path.rsplit('/', 1)[1], 'build_available': True, 'updated_at': time.time(),
                          'agents': {'designer': {'status': 'completed'}, 'developer': {'status': 'completed'}}, 'events': {}}
            elif path.startswith(('/open/', '/runtime/')):
                result = {'project': path.split('/')[2], 'status': 'stopped', 'revision': 1, 'serverId': 'mock'}
            elif path.startswith('/qa/'):
                result = {'project': path.rsplit('/', 1)[1]}
            elif path == '/settings':
                if route.request.method == 'POST':
                    body = route.request.post_data_json
                    calls.append(body)
                    for key, value in body.items():
                        if key in {'aws_profile', 'aws_region'}:
                            credentials[key] = value
                        else:
                            credentials[key + '_set'] = value != '-'
                result = {'deploy': credentials, 'admin': False}
            elif path.startswith('/deploy-results/'):
                name = path.rsplit('/', 1)[1]
                result = {'project': name, 'agent': {'listening': True}, 'stack': 'nextjs', 'settings': credentials,
                          'customization': {'project_name': name + '-site', 'repository_name': name + '-repo'}}
                if name == 'alpha':
                    result['last'] = {'run_id': 'alpha-run', 'state': 'LIVE', 'target': 'netlify'}
            elif path.startswith('/deploy/runs/'):
                run_id = path.split('/')[3]
                if path.endswith('/events'):
                    result = {'events': [
                        {'event_id': 1, 'type': 'agent', 'stage': 'repair', 'message': run_id + ' activity'},
                        {'event_id': 2, 'type': 'tool', 'stage': 'repair', 'status': 'running', 'message': 'read_file package.json', 'data': {'tool_call_id': 'read-package'}},
                        {'event_id': 3, 'type': 'tool', 'stage': 'repair', 'status': 'complete', 'message': 'read_file package.json', 'data': {'tool_call_id': 'read-package'}},
                        *[{'event_id':i, 'type':'log', 'stage':'planner', 'status':'running', 'message':'Receiving deployment plan'} for i in range(4,7)],
                    ]}
                elif path.endswith('/artifacts'):
                    result = {'artifacts': []}
                elif path.endswith('/evidence'):
                    result = {'evidence': []}
            elif path == '/deploy/jobs':
                body = route.request.post_data_json
                key = str(len(jobs) + 1)
                output = {'connected': False}
                if body['path'] == '/onboarding/status':
                    output = {'github_authenticated': True, 'aws_profiles': [aws_profile],
                              'aws_identities': {aws_profile: {'role_name': 'DeploymentRole'}}
                              if credentials['aws_profile'] == aws_profile else {}}
                jobs[key] = output
                result = {'job_id': key}
            elif path.startswith('/deploy/jobs/'):
                result = {'status': 'done', 'http_status': 200, 'result': jobs[path.rsplit('/', 1)[1]]}
            elif path == '/deploy-start':
                calls.append(route.request.post_data_json)
                result = {'state': 'STARTING'}
            await route.fulfill(content_type='application/json', body=json.dumps(result))
        await page.route('**/__agentforge/api/**', handle)
        await page.route_web_socket('**/__agentforge/ws', lambda ws: ws.on_message(lambda _: None))
        try:
            await page.goto(os.environ.get('STUDIO_TEST_URL', 'http://127.0.0.1:3000/__agentforge'), wait_until='networkidle')
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('alpha', exact=True).first.click()
            await page.get_by_role('button', name='Deploy', exact=True).first.click()
            await expect(page.get_by_role('textbox', name='Continue this project')).to_have_count(0)
            stream = page.get_by_role('region', name='Deployment agent activity', exact=True)
            await expect(stream.get_by_role('textbox')).to_have_count(0)
            await expect(stream.get_by_text('Deployment chat', exact=True)).to_be_visible()
            await expect(stream.get_by_text('read_file package.json', exact=True)).to_have_count(1)
            await expect(stream.get_by_text('Receiving deployment plan', exact=True)).to_have_count(1)
            assert await stream.evaluate("element => !!element.previousElementSibling?.querySelector('button')"), 'Chat must follow the live log tabs'
            await expect(page.get_by_role('button', name='Netlify', exact=False).first).to_be_visible()
            await expect(page.get_by_role('button', name='Azure App Service', exact=False).first).to_be_visible()
            await expect(page.get_by_role('button', name='Redeploy to Netlify')).to_be_visible()
            await page.get_by_role('button', name='Azure App Service', exact=False).first.click()
            await expect(page.get_by_label('Resource group', exact=True)).to_be_visible()
            await expect(page.get_by_role('combobox', name='App Service plan size', exact=True)).to_be_visible()
            await page.get_by_role('button', name='Netlify', exact=False).first.click()
            await expect(page.get_by_text('alpha-run activity', exact=False)).to_be_visible()
            await page.get_by_role('checkbox', name='Deploy anyway', exact=False).check()
            await page.get_by_role('button', name='Redeploy to Netlify').click()
            assert calls[-1]['target'] == 'netlify', calls
            await page.get_by_role('button', name='Settings', exact=True).first.click()
            await page.get_by_role('button', name='Integrations', exact=True).click()
            await page.get_by_role('button', name='Deployment accounts', exact=False).click()
            for title, value in [('Netlify', 'test-netlify-value'), ('Azure', json.dumps({'clientId': 'test', 'clientSecret': 'test-secret', 'tenantId': 'test', 'subscriptionId': 'test'}))]:
                row = page.locator('div.rounded-xl').filter(has=page.get_by_text(title, exact=True)).filter(has=page.get_by_role('button', name='Save credentials')).last
                await row.locator('input').fill(value)
                await row.get_by_role('button', name='Save credentials').click()
                await expect(row.locator('input')).to_have_value('')
            assert any('netlify_token' in call for call in calls)
            assert any('azure_credentials' in call for call in calls)
            aws_row = page.locator('div.rounded-xl').filter(has=page.get_by_text('AWS', exact=True)).filter(has=page.get_by_role('button', name='Use this profile')).last
            await aws_row.locator('select').filter(has=page.locator(f'option[value="{aws_profile}"]')).first.select_option(aws_profile)
            await aws_row.get_by_role('button', name='Use this profile').click()
            await expect(aws_row.get_by_text(f'profile {aws_profile} · DeploymentRole', exact=False)).to_be_visible()
            await page.keyboard.press('Escape')
            await page.get_by_role('button', name='AWS EC2', exact=False).first.click()
            await expect(page.get_by_text(f'profile {aws_profile} · DeploymentRole', exact=False)).to_be_visible()
            await expect(page.get_by_role('button', name='Deploy to AWS EC2', exact=True)).to_be_enabled()
            await page.get_by_role('button', name='Projects', exact=False).first.click()
            await page.get_by_text('beta', exact=True).first.click()
            await page.get_by_role('button', name='Deploy', exact=True).first.click()
            await expect(page.get_by_text('alpha-run activity', exact=False)).to_have_count(0)
            await expect(page.get_by_role('button', name='Redeploy to Netlify')).to_have_count(0)
            assert not errors, errors
            print('PASS: read-only deployment chat below live logs, tool progress merges into one card, account refresh and project isolation; no page exceptions')
        except Exception:
            await page.screenshot(path=str(Path(__file__).parent / 'results/deployment-browser-failure.png'), full_page=True, timeout=5000)
            print((await page.locator('body').inner_text())[:3500])
            raise
        finally:
            await asyncio.wait_for(browser.close(), timeout=5)


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=90))
