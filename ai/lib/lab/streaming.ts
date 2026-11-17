/** Extract only the top-level studentMessage string from provisional JSON. */
function stringAt(text:string,start:number){
 let value='';
 for(let i=start+1;i<text.length;i++){
  const c=text[i];
  if(c==='"')return {value,end:i+1,complete:true};
  if(c==='\\'){
   if(i+1>=text.length)break;
   const next=text[++i];
   if(next==='u'){
    const hex=text.slice(i+1,i+5);if(!/^[0-9a-fA-F]{4}$/.test(hex))break;
    value+=String.fromCharCode(parseInt(hex,16));i+=4;
   }else{
    const escaped:Record<string,string>={'"':'"','\\':'\\','/':'/','n':'\n','r':'\r','t':'\t','b':'\b','f':'\f'};
    if(!(next in escaped))break;value+=escaped[next];
   }
  }else value+=c;
 }
 // Do not emit half a surrogate pair while a Unicode escape is arriving.
 if(value.length&&/[\uD800-\uDBFF]/.test(value[value.length-1]))value=value.slice(0,-1);
 return {value,end:text.length,complete:false};
}
export function studentMessagePrefix(text:string):string{
 let depth=0;
 for(let i=0;i<text.length;i++){
  if(text[i]==='"'){
   const token=stringAt(text,i);if(!token.complete)return '';
   let j=token.end;while(/\s/.test(text[j]||'!'))j++;
   if(depth===1&&token.value==='studentMessage'&&text[j]===':'){
    j++;while(/\s/.test(text[j]||'!'))j++;
    return text[j]==='"'?stringAt(text,j).value:'';
   }
   i=token.end-1;
  }else if(text[i]==='{')depth++;
  else if(text[i]==='}')depth--;
 }
 return '';
}
export async function readStructuredStream(response:Response,onText:(text:string)=>void){
 if(!response.body)throw new Error('Provider stream has no body.');
 const reader=response.body.getReader(),decoder=new TextDecoder();
 let buffer='',content='',emitted='',finishReason:string|null=null,usage:Record<string,number>={};
 function line(value:string){
  if(!value.startsWith('data:'))return;
  const data=value.slice(5).trim();if(!data||data==='[DONE]')return;
  const event=JSON.parse(data);
  if(event.error)throw new Error('Provider stream failed.');
  if(event.usage)usage=event.usage;
  const choice=event.choices?.[0];if(choice?.finish_reason)finishReason=choice.finish_reason;
  if(typeof choice?.delta?.content==='string'){
   content+=choice.delta.content;
   const prefix=studentMessagePrefix(content);
   if(!prefix.startsWith(emitted))throw new Error('Stream text changed unexpectedly.');
   const delta=prefix.slice(emitted.length);if(delta)onText(delta);emitted=prefix;
  }
 }
 try{
  for(;;){const {value,done}=await reader.read();buffer+=decoder.decode(value,{stream:!done});
   let end;while((end=buffer.indexOf('\n'))!==-1){line(buffer.slice(0,end).replace(/\r$/,''));buffer=buffer.slice(end+1);}
   if(done)break;
  }
  if(buffer.trim())line(buffer.trim());
 }finally{reader.releaseLock();}
 if(!finishReason)throw new Error('Provider stream ended before completion.');
 return {choices:[{finish_reason:finishReason,message:{content}}],usage};
}
