import test from 'node:test';
import assert from 'node:assert/strict';
import {studentMessagePrefix,readStructuredStream} from '../lib/lab/streaming.ts';
import {requestStructured} from '../lib/lab/structured-request.ts';

test('stream extracts only the student message and handles every Unicode/escape boundary',()=>{
 const value='中文 😀 引號 " 換行\n與反斜線 \\';
 const json=JSON.stringify({status:'continue',progress:{currentPosition:'不得顯示的進度'},studentMessage:value});
 let prior='';
 for(let i=0;i<=json.length;i++){const next=studentMessagePrefix(json.slice(0,i));assert.ok(next.startsWith(prior));assert.ok(value.startsWith(next));prior=next;}
 assert.equal(prior,value);
 assert.equal(studentMessagePrefix('{"progress":{"studentMessage":"秘密"},"studentMessage":"正式文字"}'),'正式文字');
 assert.equal(studentMessagePrefix('{"studentMessage":"\\uD83D'),'');
 assert.equal(studentMessagePrefix('{"studentMessage":"\\uD83D\\uDE00"}'),'😀');
});
function response(raw){const bytes=new TextEncoder().encode(raw);return new Response(new ReadableStream({start(c){for(const byte of bytes)c.enqueue(Uint8Array.of(byte));c.close();}}));}
test('provider SSE emits real chunks before terminal result and retains token usage',async()=>{
 const source=JSON.stringify({studentMessage:'想法\n可以改變',progress:{hidden:'不可顯示'}});
 const frames=[': keepalive\n\n',...[...source].map(c=>'data: '+JSON.stringify({choices:[{delta:{content:c}}]})+'\n\n'),'data: '+JSON.stringify({choices:[{delta:{},finish_reason:'stop'}]})+'\n\n','data: '+JSON.stringify({choices:[],usage:{total_tokens:17}})+'\n\n','data: [DONE]\n\n'].join('');
 const chunks=[];const body=await readStructuredStream(response(frames),text=>chunks.push(text));
 assert.equal(chunks.join(''),'想法\n可以改變');assert.ok(chunks.length>1);assert.equal(body.usage.total_tokens,17);assert.equal(body.choices[0].message.content,source);
});
test('truncated stream and provider error never return a successful result',async()=>{
 await assert.rejects(()=>readStructuredStream(response('data: {"choices":[{"delta":{"content":"{}"}}]}\n\n'),()=>{}),/before completion/);
 await assert.rejects(()=>readStructuredStream(response('data: {"error":{"message":"bad"}}\n\n'),()=>{}),/failed/);
});
test('structured transport opts into provider streaming only for a text callback',async()=>{
 const chunks=[];
 const frames='data: '+JSON.stringify({choices:[{delta:{content:'{"studentMessage":"回答"}'},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n';
 const result=await requestStructured({name:'dialogue_turn',instructions:'test',input:{},schema:{},model:'openai/gpt-4.1-mini',apiKey:'test-key',siteUrl:'http://localhost',onText:t=>chunks.push(t)},async(_,options)=>{const data=JSON.parse(options.body);assert.equal(data.stream,true);return response(frames);});
 assert.equal(result.decoded.studentMessage,'回答');assert.equal(chunks.join(''),'回答');
});
