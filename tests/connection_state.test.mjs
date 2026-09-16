import assert from 'node:assert/strict';
import connection from '../locallink/static/connection-state.js';

assert.deepEqual(connection.classify(null, null, null), {state:'failed', error:'OFFLINE'});
assert.deepEqual(
  connection.classify({ok:true,service:'other',id:'x'}, null, null),
  {state:'failed',error:'NOT_LOCALLINK'},
);
assert.deepEqual(
  connection.classify({ok:true,service:'locallink',id:'x'}, {ok:false,status:401}, null),
  {state:'failed',error:'PAIRING_REJECTED'},
);
assert.deepEqual(
  connection.classify({ok:true,service:'locallink',id:'new-id'}, {ok:true}, {id:'old-id'}),
  {state:'retrust_required',error:'IDENTITY_CHANGED'},
);
assert.deepEqual(
  connection.classify({ok:true,service:'locallink',id:'same'}, {ok:true}, {id:'same'}),
  {state:'ready',error:null},
);

assert.equal(
  connection.resolveTrustedUrl(
    {id:'phone-id',url:'http://192.168.1.20:53317/?code=123456'},
    [{id:'phone-id',ip:'192.168.1.82',port:53317}],
  ),
  'http://192.168.1.82:53317/?code=123456',
);

assert.equal(
  connection.resolveTrustedUrl(
    {id:'phone-id',url:'http://192.168.1.20:53317/?code=123456'},
    [{id:'other-id',ip:'192.168.1.82',port:53317}],
  ),
  'http://192.168.1.20:53317/?code=123456',
);
console.log('connection state tests passed');
