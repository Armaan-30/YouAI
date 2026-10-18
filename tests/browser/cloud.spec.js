const { test, expect } = require('@playwright/test');
const fs = require('fs');

test('hosted interface hides laptop controls and explains server storage', async ({page})=>{
  await page.route('**/api/status',r=>r.fulfill({json:{llm_ready:true,cloud:true,provider:'groq',speech_provider:'groq',model:'qwen/qwen3.8-27b'}}));
  await page.route('http://127.0.0.1:8766/',async r=>{
    const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('<body>','<body data-cloud="true">')});
  });
  await page.goto('/');
  await expect(page.locator('#sign-out')).toBeVisible();
  await expect(page.locator('#wake')).toBeEnabled();
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
async function hostedWakePage(page){
 await page.addInitScript(()=>{
   window.instances=[];
   window.SpeechRecognition=class {
     start(){window.instances.push(this);this.onstart?.();}
     abort(){this.aborted=true;}
     emit(text){const result=[{transcript:text}];result.isFinal=true;this.onresult?.({resultIndex:0,results:[result]});}
   };
 });
 await page.route('**/api/status',r=>r.fulfill({json:{llm_ready:true,cloud:true,provider:'groq',speech_provider:'groq',model:'test'}}));
 await page.route('http://127.0.0.1:8766/',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('<body>','<body data-cloud="true">')});});
 await page.goto('/');
 await page.evaluate(()=>{document.getElementById('speak').checked=false;});
}

test('hosted Hey You submits the command once and stops listening when disabled',async({page})=>{
 await hostedWakePage(page);
 const prompts=[];
 await page.route('**/api/chat/stream',r=>{prompts.push(r.request().postDataJSON().text);return r.fulfill({contentType:'application/x-ndjson',body:JSON.stringify({type:'done',text:'Hello there.'})+'\n'});});
 await page.locator('label.wake').click();
 await expect(page.locator('#state')).toContainText('Listening for');
 await expect.poll(()=>page.evaluate(()=>instances.length)).toBe(1);
 await page.evaluate(()=>instances[0].emit('unrelated conversation'));
 expect(prompts).toEqual([]);
 await page.evaluate(()=>instances[0].emit('Hey you, tell me a joke'));
 await expect.poll(()=>prompts.length).toBe(1);expect(prompts[0]).toBe('tell me a joke');
 await expect.poll(()=>page.evaluate(()=>instances.length)).toBe(2);
 await page.locator('label.wake').click();
 await expect(page.locator('#state')).toHaveText('Tap to talk');
 expect(await page.evaluate(()=>instances.every(i=>i.aborted))).toBeTruthy();
});

test('hosted bare wake phrase accepts a following command and permission errors recover',async({page})=>{
 await hostedWakePage(page);
 const prompts=[];
 await page.route('**/api/chat/stream',r=>{prompts.push(r.request().postDataJSON().text);return r.fulfill({contentType:'application/x-ndjson',body:JSON.stringify({type:'done',text:'Okay.'})+'\n'});});
 await page.locator('label.wake').click();await expect.poll(()=>page.evaluate(()=>instances.length)).toBe(1);
 await page.evaluate(()=>instances[0].emit('Hey You.'));
 await expect(page.locator('#state')).toHaveText('I’m listening');
 await page.evaluate(()=>instances[0].emit('What can you do?'));
 await expect.poll(()=>prompts.length).toBe(1);expect(prompts[0]).toBe('What can you do?');
 await expect.poll(()=>page.evaluate(()=>instances.length)).toBe(2);
 await page.evaluate(()=>instances[1].onerror({error:'not-allowed'}));
 await expect(page.locator('#wake')).not.toBeChecked();
 await expect(page.locator('#error')).toContainText('Allow microphone');
 await expect(page.locator('#state')).toHaveText('Tap to talk');
});

test('unsupported hosted wake browser gives a usable fallback',async({page})=>{
 await hostedWakePage(page);
 await page.evaluate(()=>{window.SpeechRecognition=undefined;window.webkitSpeechRecognition=undefined;});
 await page.locator('label.wake').click();
 await expect(page.locator('#error')).toContainText('microphone button');
 await expect(page.locator('#wake')).not.toBeChecked();
});
