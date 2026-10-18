const { test, expect } = require('@playwright/test');
const fs = require('fs');

test('hosted interface hides laptop controls and explains server storage', async ({page})=>{
  await page.route('**/api/status',r=>r.fulfill({json:{llm_ready:true,cloud:true,provider:'groq',speech_provider:'groq',model:'qwen/qwen3.8-27b'}}));
  await page.route('http://127.0.0.1:8766/',async r=>{
    const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('<body>','<body data-cloud="true">')});
  });
  await page.goto('/');
  await expect(page.locator('#sign-out')).toBeVisible();
  await expect(page.locator('#wake')).toBeDisabled();
  await expect(page.locator('#processing-location')).toContainText('server');
  await page.locator('#open-panel').click();
  await expect(page.locator('#laptop-actions')).toBeHidden();
  await expect(page.locator('#storage-note')).toContainText('private account');
  await expect(page.locator('#document-help')).toContainText('keywords');
  await expect(page.locator('#barge-in')).toBeDisabled();
  await page.locator('#close-panel').click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('sign-in form reports errors without exposing credentials', async ({page})=>{
  await page.route('**/login',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync('web/login.html','utf8')}));
  await page.route('**/api/auth/login',r=>r.fulfill({status:400,json:{detail:'Check username and password.'}}));
  await page.goto('/login');
  await page.locator('#username').fill('alice');await page.locator('#password').fill('example-password');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('#login-error')).toHaveText('Check username and password.');
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeEnabled();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'.runtime/cloud-login.png',fullPage:true});
});
