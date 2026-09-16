import assert from 'node:assert/strict';
import model from '../locallink/static/ui-model.js';

const longText = 'LocalLink '.repeat(80) + '\nhttps://example.com/docs';
const text = model.historyItem({
  id: 't1', kind: 'text', text: longText, sender: 'Phone', receiver: 'PC',
  created_at: 1, size_human: '1 KB', actions: ['read', 'copy'],
});
assert.equal(text.displayKind, 'text');
assert.equal(text.summary, longText);
assert.deepEqual(text.actions, ['read', 'copy', 'delete']);

const office = model.historyItem({
  id: 'f1', kind: 'file', name: 'quarterly.pptx', sender: 'PC', receiver: 'Phone',
  created_at: 1, size_human: '2 MB', category: 'presentation',
  actions: ['preview_convert', 'open_external', 'download'], available: true,
});
assert.equal(office.displayKind, 'presentation');
assert.deepEqual(office.actions, ['preview_convert', 'open_external', 'download', 'delete']);
assert.equal(model.previewUrl(office, '123 456'), '/api/preview/f1?format=pdf&code=123%20456');

const missing = model.historyItem({
  id: 'f2', kind: 'file', name: 'gone.zip', actions: ['download'], available: false,
});
assert.deepEqual(missing.actions, ['delete']);

const legacy = model.historyItem({id:'legacy',kind:'file'});
assert.equal(legacy.sha256, '');
assert.equal(legacy.size_human, '0 B');
assert.equal(legacy.created_at, 0);
assert.deepEqual(model.historyItem({id:'bad',kind:'file',actions:{download:true}}).actions,['download','delete']);
assert.deepEqual(model.historyItem({id:'bad-text',kind:'text',actions:'read'}).actions,['read','copy','delete']);
const records = Array.from({length:45}, (_,i)=>({id:String(i),kind:i%2?'text':'file',text:'会议笔记',name:`File ${i}`,created_at:i,size:i*10,category:i%2?'text':'image'}));
const page = model.selectHistory(records,{page:2});
assert.equal(page.items.length,20);
assert.equal(page.items[0].id,'24');
assert.equal(page.pages,3);
assert.equal(model.selectHistory(records,{page:9}).page,3);
assert.equal(model.selectHistory(records,{filter:'image'}).total,23);
assert.equal(model.selectHistory(records,{query:' FILE 44 '}).total,1);
assert.equal(model.selectHistory(records,{sort:'oldest'}).items[0].id,'0');
assert.equal(model.selectHistory(records,{sort:'largest'}).items[0].id,'44');
assert.equal(model.selectHistory([null,{id:'gone',kind:'file',available:false}],{filter:'missing'}).total,1);
assert.equal(model.selectHistory([],{page:99}).page,1);
console.log('web ui model tests passed');
