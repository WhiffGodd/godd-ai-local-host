"use strict";
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=fs.readFileSync('public/ai-videos.js','utf8').replace(/\ninitialize\(\);\s*$/,'');
function studio(fetch){
  const elements=new Map();const saved=new Map();const workbench={dataset:{generated:'true'}};
  function element(id){
    if(!elements.has(id))elements.set(id,{value:'60',hidden:false,disabled:false,textContent:'',dataset:{},listeners:{},
      addEventListener(type,callback){this.listeners[type]=callback;},setAttribute(name,value){this[name]=value;},
      removeAttribute(name){delete this[name];},pause(){},load(){},querySelectorAll(){return [];}});
    return elements.get(id);
  }
  const context=vm.createContext({fetch,AbortSignal,URL,console,setTimeout,clearTimeout,
    document:{getElementById:element,querySelector:()=>workbench,querySelectorAll:()=>[]},
    sessionStorage:{setItem:(key,value)=>saved.set(key,value),getItem:key=>saved.get(key)}});
  vm.runInContext(source,context);
  vm.runInContext("page.generation='saved-video';page.provider={available:true};page.templates=[{}];",context);
  element('prompt').value='Keep this exact electrical prompt';element('video').src='/old-video';element('downloadVideo').href='/old-download';
  return {context,element,saved};
}
(async()=>{
  const missing=studio(async()=>({ok:false,status:404,json:async()=>({error:'Unavailable',code:'AI_VIDEO_NOT_FOUND'})}));
  await vm.runInContext('watchGeneration()',missing.context);
  assert.equal(vm.runInContext('page.generation',missing.context),null);
  assert.equal(missing.element('prompt').value,'Keep this exact electrical prompt');
  assert.equal(missing.element('video').hidden,true);assert.equal(missing.element('video').src,undefined);
  assert.equal(missing.element('downloadVideo').href,undefined);assert.equal(missing.element('exportTools').hidden,true);
  assert.equal(missing.element('generate').disabled,false);assert.equal(missing.element('checkGeneration').hidden,true);
  assert.match(missing.element('generationStatus').textContent,/prompt and settings are kept/);
  assert.equal(JSON.parse([...missing.saved.values()][0]).prompt,'Keep this exact electrical prompt');
  const interrupted=studio(async()=>({ok:true,status:200,json:async()=>({state:'failed',code:'GENERATION_INTERRUPTED',error:'The studio restarted. Your prompt is kept; generate it again.'})}));
  await vm.runInContext('watchGeneration()',interrupted.context);
  assert.equal(vm.runInContext('page.generation',interrupted.context),null);
  assert.equal(interrupted.element('generate').disabled,false);
  const offline=studio(async()=>{throw new Error('Network offline');});
  await vm.runInContext('watchGeneration()',offline.context);
  assert.equal(vm.runInContext('page.generation',offline.context),'saved-video');
  assert.equal(offline.element('checkGeneration').hidden,false);
  assert.equal(offline.element('prompt').value,'Keep this exact electrical prompt');
  const uploaded=studio(async()=>({ok:true,status:200,json:async()=>({state:'uploaded',video_id:'abcdefghijk'})}));
  await vm.runInContext('watchGeneration()',uploaded.context);
  assert.equal(vm.runInContext('page.generation',uploaded.context),null);
  assert.match(uploaded.element('generationStatus').textContent,/local copy was deleted/);
  assert.equal(uploaded.element('exportTools').hidden,true);
  console.log('PASS: stale links and interrupted renders clear unusable controls, preserve the prompt, and allow regeneration; temporary network errors preserve reconnection');
})().catch(error=>{console.error(error);process.exitCode=1;});
