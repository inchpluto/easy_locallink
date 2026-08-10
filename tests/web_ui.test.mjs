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

console.log('web ui model tests passed');
