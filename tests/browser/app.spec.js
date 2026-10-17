const { test, expect } = require("@playwright/test");

test.beforeEach(async ({page}) => {
  await page.route("**/api/status", route=>route.fulfill({json:{llm_ready:true,model:"test-local"}}));
  await page.route("**/api/history", route=>route.fulfill({json:{messages:[]}}));
  await page.route("**/api/notes", route=>route.fulfill({json:{notes:[]}}));
  await page.route("**/api/reminders", route=>route.fulfill({json:{reminders:[],now:Date.now()/1000,timezone:"Asia/Kolkata"}}));
  await page.goto("/");
});

test("minimal home, typed answer and transcript controls", async ({page}) => {
  const errors=[]; page.on("pageerror",e=>errors.push(e.message));
  await expect(page.getByRole("heading",{name:"A thought away."})).toBeVisible();
  await expect(page.locator("#wake")).not.toBeChecked();
  await page.getByRole("button",{name:"Open conversation and settings"}).click();
  await page.locator("#speak").uncheck();
  await page.getByRole("button",{name:"Close conversation"}).click();
  await page.route("**/api/chat/stream", async route=>{
    expect(route.request().postDataJSON().text).toBe("Hello");
    await route.fulfill({contentType:"application/x-ndjson",body:
      JSON.stringify({type:"token",text:"Hello. What’s on your mind?"})+"\n"+
      JSON.stringify({type:"done",text:"Hello. What’s on your mind?"})+"\n"});
  });
  await page.locator("#prompt").fill("Hello");
  await page.getByRole("button",{name:"Send message"}).click();
  await expect(page.locator("#latest-text")).toHaveText("Hello. What’s on your mind?");
  await expect(page.locator("#state")).toHaveText("Tap to talk");
  expect(errors).toEqual([]);
});

test("microphone denial gives a useful recovery message", async ({page})=>{
  await page.evaluate(()=>{ navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException("Denied","NotAllowedError")}; });
  await page.getByRole("button",{name:"Start listening",exact:true}).click();
  await expect(page.locator("#error")).toContainText("Allow microphone access");
  await expect(page.locator("#state")).toHaveText("Tap to talk");
});

test('Groq mode clearly discloses remote context and audio processing',async({page})=>{
 await page.route('**/api/status',route=>route.fulfill({json:{llm_ready:true,provider:'groq',speech_provider:'groq',model:'qwen/qwen3.8-27b'}}));
 await page.reload();
 await expect(page.locator('#connection')).toContainText('Groq connected');
 await expect(page.locator('#provider-notice')).toBeVisible();
 await expect(page.locator('#provider-notice')).toContainText('approved memories and document passages');
 await expect(page.locator('#provider-notice')).toContainText('Voice requests are uploaded');
 await expect(page.locator('#processing-location')).toContainText('Groq online processing');
});

test("cancellation ignores a stale model reply",async({page})=>{
  await page.route("**/api/chat/stream",async route=>{
    await new Promise(resolve=>setTimeout(resolve,1200));
    await route.fulfill({contentType:"application/x-ndjson",body:JSON.stringify({type:"done",text:"This must not appear"})+"\n"}).catch(()=>{});
  });
  await page.route("**/api/cancel/**",route=>route.fulfill({json:{ok:true}}));
  await page.locator("#prompt").fill("Think");
  await page.getByRole("button",{name:"Send message"}).click();
  await expect(page.locator("#state")).toHaveText("Thinking with you");
  await page.getByRole("button",{name:"Stop",exact:true}).click();
  await expect(page.locator("#state")).toHaveText("Tap to talk");
  await page.waitForTimeout(1500);
  await expect(page.locator("#latest")).toBeHidden();
});

test("desktop and phone layouts have no horizontal overflow",async({page})=>{
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:".runtime/youai-desktop.png",fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:".runtime/youai-mobile.png",fullPage:true});
});

test("speaks a complete sentence before the answer stream finishes",async({page})=>{
  await page.evaluate(()=>{
    window.spoken=[];
    say=async text=>{window.spoken.push(text);};
    const original=window.fetch;
    window.fetch=(url,options)=>{
      if(url!=="/api/chat/stream") return original(url,options);
      const encoder=new TextEncoder();
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(JSON.stringify({type:"token",text:"Here is the first complete sentence. "})+"\n"));
          window.finishResponse=()=>{
            controller.enqueue(encoder.encode(JSON.stringify({type:"token",text:"And here is the rest."})+"\n"));
            controller.enqueue(encoder.encode(JSON.stringify({type:"done",text:"Here is the first complete sentence. And here is the rest."})+"\n"));
            controller.close();
          };
        }
      }),{headers:{"Content-Type":"application/x-ndjson"}}));
    };
  });
  await page.locator("#prompt").fill("Tell me something");
  await page.getByRole("button",{name:"Send message"}).click();
  await expect.poll(()=>page.evaluate(()=>window.spoken.length)).toBe(1);
  await expect(page.locator("#latest-text")).toHaveText("Here is the first complete sentence. ");
  await page.evaluate(()=>window.finishResponse());
  await expect.poll(()=>page.evaluate(()=>window.spoken.length)).toBe(2);
  await expect(page.locator("#state")).toHaveText("Tap to talk");
});

test("wake hands the request to transcription without a second microphone acquisition",async({page})=>{
  await page.evaluate(()=>{
    window.starts=0;
    YouAudio=class {
      constructor(callbacks){this.callbacks=callbacks;}
      async start(wake){window.starts++;window.capture=this;}
      close(){this.closed=true;}
    };
    say=async()=>{};
  });
  await page.route("**/api/transcribe",route=>route.fulfill({json:{text:"Hey you, show my notes."}}));
  let prompt;
  await page.route("**/api/chat/stream",route=>{
    prompt=route.request().postDataJSON().text;
    return route.fulfill({body:JSON.stringify({type:"token",text:"Your notes."})+"\n"+JSON.stringify({type:"done",text:"Your notes."})+"\n"});
  });
  await page.locator("label.wake").click();
  await expect.poll(()=>page.evaluate(()=>window.starts)).toBe(1);
  await page.evaluate(()=>{
    window.capture.callbacks.onWake();
    // Turn off automatic re-arming so we can count just the handoff.
    document.getElementById("wake").checked=false;
    window.capture.callbacks.onAudio(new Blob(["audio"]),true);
  });
  await expect(page.locator("#latest-text")).toHaveText("Your notes.");
  expect(prompt).toBe("show my notes.");
  expect(await page.evaluate(()=>window.starts)).toBe(1);
});

test("overdue reminders are visible after reopening and can be completed",async({page})=>{
  await page.route("**/api/reminders",route=>route.fulfill({json:{
    reminders:[{id:42,content:"Drink water",due_at:1}],now:10,timezone:"Asia/Kolkata"}}));
  await page.route("**/api/reminders/42/done",async route=>{
    await page.route("**/api/reminders",r=>r.fulfill({json:{reminders:[],now:10,timezone:"Asia/Kolkata"}}));
    await route.fulfill({json:{ok:true}});
  });
  await page.evaluate(()=>refreshReminders());
  await expect(page.locator("#reminder-alert")).toContainText("Drink water");
  await page.locator("#due-reminders").getByRole("button",{name:"Done"}).click();
  await expect(page.locator("#reminder-alert")).toBeHidden();
});

test("document import enables retrieval and safely renders sources", async ({page})=>{
  let imported=false;
  await page.route("**/api/documents",route=>{
    if(route.request().method()==="POST"){ expect(route.request().postData()).toContain('eng+hin');imported=true;return route.fulfill({json:{id:1,warnings:[],duplicate:false}}); }
    return route.fulfill({json:{documents:imported?[{id:1,name:"facts.txt",chunks:1,warnings:[]}]:[]}});
  });
  await page.getByRole("button",{name:"Open conversation and settings"}).click();
  await page.locator("#speak").uncheck();
  await page.locator('#ocr-language').selectOption('eng+hin');
  await page.locator("#document-file").setInputFiles({name:"facts.txt",mimeType:"text/plain",buffer:Buffer.from("Launch is November 12.")});
  await page.locator("#import-document").click();
  await expect(page.locator("#document-status")).toContainText("Ready to search");
  await expect(page.locator("#use-documents")).toBeChecked();
  await page.getByRole("button",{name:"Close conversation"}).click();
  await page.route("**/api/chat/stream",route=>{
    expect(route.request().postDataJSON().use_documents).toBe(true);
    return route.fulfill({contentType:"application/x-ndjson",body:[
      {type:"sources",sources:[{label:"S1",name:"facts.txt",page:1,excerpt:"<script>evil()</script> Launch is November 12."}]},
      {type:"token",text:"November 12. [S1]"},{type:"done",text:"November 12. [S1]"}
    ].map(x=>JSON.stringify(x)).join("\n")+"\n"});
  });
  await page.locator("#prompt").fill("When is launch?");await page.getByRole("button",{name:"Send message"}).click();
  await expect(page.locator("#sources summary")).toContainText("facts.txt");
  expect(await page.locator("#sources script").count()).toBe(0);
});

test('document summary consumes progress events and displays its final result',async({page})=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/documents?*',route=>route.fulfill({json:{documents:[{id:42,name:'long.txt',chunks:20,warnings:[]}]}}));
 await page.locator('#open-panel').click();await page.locator('#speak').uncheck();
 await page.route('**/api/chat/stream',route=>{
  expect(route.request().postDataJSON().summary_document).toBe(42);
  return route.fulfill({contentType:'application/x-ndjson',body:[
   {type:'progress',text:'Read section 1 of 7'},
   {type:'token',text:'Summary covers all indexed passages.'},
   {type:'done',text:'Summary covers all indexed passages.'}
  ].map(event=>JSON.stringify(event)).join('\n')+'\n'});
 });
 await page.getByRole('button',{name:'Summarize',exact:true}).click();
 await expect(page.locator('#latest-text')).toHaveText('Summary covers all indexed passages.');
 expect(errors).toEqual([]);
});

test("Android bridge authenticates API calls and completes native speech",async({page})=>{
  await page.addInitScript(()=>{
    window.NativeYou={getToken:()=>"test-pairing-token",stop:()=>{},speak:(text,id)=>{window.lastNativeSpeech=text;setTimeout(()=>window.onYouSpeech(id),10);}};
  });
  await page.route("**/api/status",route=>{
    expect(route.request().headers().authorization).toBe("Bearer test-pairing-token");
    return route.fulfill({json:{llm_ready:true,model:"test"}});
  });
  await page.goto("/");
  await page.route("**/api/chat/stream",route=>{
    expect(route.request().headers().authorization).toBe("Bearer test-pairing-token");
    return route.fulfill({contentType:"application/x-ndjson",body:'{"type":"token","text":"Hello from your laptop."}\n{"type":"done","text":"Hello from your laptop."}\n'});
  });
  await page.locator("#prompt").fill("Hello");await page.getByRole("button",{name:"Send message"}).click();
  await expect.poll(()=>page.evaluate(()=>window.lastNativeSpeech)).toBe("Hello from your laptop.");
  await expect(page.locator("#state")).toHaveText("Tap to talk");
});

test("memory requires explicit save and supports edit and delete",async({page})=>{
 let memories=[];
 await page.route('**/api/memories**',async route=>{
  const req=route.request(),method=req.method();
  if(method==='POST'){expect(req.postDataJSON().approved).toBe(true);memories=[{id:1,content:req.postDataJSON().content}];}
  if(method==='PUT')memories[0].content=req.postDataJSON().content;
  if(method==='DELETE')memories=[];
  return route.fulfill({json:method==='GET'?{memories}:{ok:true,id:1}});
 });
 await page.locator('#open-panel').click();await page.locator('#memory-text').fill('I prefer tea.');
 await expect(page.locator('#memories')).toBeEmpty();
 await page.locator('#memory-form button').click();await expect(page.locator('#memories')).toContainText('I prefer tea.');
 page.once('dialog',dialog=>dialog.accept('I prefer coffee.'));await page.getByRole('button',{name:'Edit',exact:true}).click();await expect(page.locator('#memories')).toContainText('I prefer coffee.');
 page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Forget',exact:true}).click();await expect(page.locator('#memories')).toBeEmpty();
});

test('document selection is sent and web mode is mutually exclusive',async({page})=>{
 await page.route('**/api/documents*',route=>route.fulfill({json:{documents:[{id:7,name:'launch.txt',chunks:1,warnings:[]}]}}));
 await page.locator('#open-panel').click();await page.locator('#speak').uncheck();await page.getByLabel('Use launch.txt',{exact:true}).check();await page.locator('#close-panel').click();await page.locator('#use-documents').check();
 await page.route('**/api/chat/stream',route=>{
  expect(route.request().postDataJSON().document_ids).toEqual([7]);
  return route.fulfill({contentType:'application/x-ndjson',body:'{"type":"token","text":"Found."}\n{"type":"done","text":"Found."}\n'});
 });
 await page.locator('#prompt').fill('When?');await page.getByRole('button',{name:'Send message'}).click();await expect(page.locator('#latest-text')).toHaveText('Found.');
 await page.locator('#use-web').check();await expect(page.locator('#use-documents')).not.toBeChecked();await expect(page.locator('#error')).toContainText('sent to external search');
});

test('file creation waits for explicit confirmation',async({page})=>{
 let confirmed=false;
 await page.route('**/api/desktop/permissions',route=>route.fulfill({json:{permissions:[{id:1,kind:'folder',path:'C:/Chosen'}]}}));
 await page.route('**/api/desktop/preview',route=>route.fulfill({json:{token:'preview-token',preview:'Create C:/Chosen/hello.txt\nHello'}}));
 await page.route('**/api/desktop/confirm',route=>{confirmed=true;expect(route.request().postDataJSON()).toEqual({token:'preview-token',approved:true});return route.fulfill({json:{message:'Created hello.txt'}});});
 await page.locator('#open-panel').click();await page.locator('#action-operation').selectOption('create');await page.locator('#action-name').fill('hello.txt');await page.locator('#action-content').fill('Hello');await page.locator('#action-form button').click();
 await expect(page.locator('#action-result')).toContainText('Create C:/Chosen');expect(confirmed).toBe(false);
 await page.locator('#action-confirm').click();await expect(page.locator('#action-result')).toHaveText('Created hello.txt');expect(confirmed).toBe(true);
});


test('remember command proposes a memory without saving it',async({page})=>{
 let saved=false;await page.route('**/api/memories',route=>{if(route.request().method()==='POST')saved=true;return route.fulfill({json:{memories:[]}});});
 await page.locator('#prompt').fill('Remember that I prefer tea');await page.getByRole('button',{name:'Send message'}).click();
 await expect(page.locator('#panel')).toBeVisible();await expect(page.locator('#memory-text')).toHaveValue('I prefer tea');expect(saved).toBe(false);
});

test('spoken interruption stops the reply and keeps the command microphone',async({page})=>{
 await page.evaluate(()=>{
  window.starts=0;
  YouAudio=class{constructor(callbacks){this.callbacks=callbacks;}async start(){window.capture=this;window.starts++;}close(){this.closed=true;}};
 });
 await page.route('**/api/transcribe',route=>route.fulfill({json:{text:'Hey you, show my notes.'}}));
 await page.route('**/api/chat/stream',route=>route.fulfill({body:'{"type":"token","text":"Your notes."}\n{"type":"done","text":"Your notes."}\n'}));
 await page.evaluate(async()=>{
  document.getElementById('speak').checked=false;
  setState('speaking');await startInterruption();await window.capture.callbacks.onWake();
 });
 await expect(page.locator('#state')).toHaveText('I’m listening');expect(await page.evaluate(()=>window.capture.closed||false)).toBe(false);
 await page.evaluate(()=>window.capture.callbacks.onAudio(new Blob(['audio'])));
 await expect(page.locator('#latest-text')).toHaveText('Your notes.');expect(await page.evaluate(()=>window.starts)).toBe(1);
});
