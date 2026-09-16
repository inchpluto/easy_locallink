function readTrusted(){try{const value=JSON.parse(localStorage.getItem('locallink-trusted')||'[]');return Array.isArray(value)?value.filter(item=>{try{return item&&['http:','https:'].includes(new URL(item.url).protocol)}catch{return false}}):[]}catch{return []}}
const state={code:new URLSearchParams(location.search).get('code')||localStorage.getItem('locallink-code')||'',status:null,query:'',filter:'all',sort:'newest',page:1,trusted:readTrusted(),sound:localStorage.getItem('locallink-sound')!=='off',historyHost:'',knownRecordIds:new Set()};
const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const formatDate=value=>Number(value)>0?new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value*1000)):'时间未知';
const apiUrl=path=>`${path}${path.includes('?')?'&':'?'}code=${encodeURIComponent(state.code)}`;
const isMobile=()=>/Android|Mobile/i.test(navigator.userAgent);
const senderName=()=>new URLSearchParams(location.search).get('client')||(isMobile()?'手机端':'电脑端');
let toastTimer;
let audioContext;
let modalReturnFocus=null;
let modalBackground=[];
function ensureAudio(){if(!state.sound)return null;try{audioContext||=new (window.AudioContext||window.webkitAudioContext)();if(audioContext.state==='suspended')audioContext.resume();return audioContext}catch{return null}}
function playSound(kind='success'){
  const context=ensureAudio();if(!context)return;const now=context.currentTime,notes=kind==='connect'?[440,660]:kind==='send'?[520,780]:[220,180];
  notes.forEach((frequency,index)=>{const oscillator=context.createOscillator(),gain=context.createGain();oscillator.type='sine';oscillator.frequency.setValueAtTime(frequency,now+index*.075);gain.gain.setValueAtTime(.0001,now+index*.075);gain.gain.exponentialRampToValueAtTime(kind==='error'?.045:.032,now+index*.075+.012);gain.gain.exponentialRampToValueAtTime(.0001,now+index*.075+.13);oscillator.connect(gain).connect(context.destination);oscillator.start(now+index*.075);oscillator.stop(now+index*.075+.14)});
  if(kind!=='error'&&navigator.vibrate)navigator.vibrate(18);
}
function updateSoundButton(){const button=$('soundButton');button.setAttribute('aria-pressed',String(state.sound));button.setAttribute('aria-label',state.sound?'关闭界面声音':'开启界面声音');button.querySelector('span').textContent=state.sound?'声音':'静音'}

const mobilePaged=true;
function setMobileView(view){
  if(!mobilePaged)return;
  const allowed=['home','send','history','devices'];
  const next=allowed.includes(view)?view:'home';
  $('app').dataset.view=next;
  document.querySelectorAll('#mobileNav button, .topbar nav a').forEach(button=>{
    const active=button.dataset.view===next;
    button.classList.toggle('active',active);
    active?button.setAttribute('aria-current','page'):button.removeAttribute('aria-current');
  });
  const reduceMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.scrollTo({top:0,behavior:reduceMotion?'auto':'smooth'});
  const pageNames={home:'主页',send:'发送页面',history:'传输记录页面',devices:'设备页面'};
  $('pageAnnouncer').textContent=`已切换到${pageNames[next]}`;
  const hashes={home:'#top',send:'#send',history:'#historySection',devices:'#network'};
  if(location.hash!==hashes[next])history.replaceState(null,'',hashes[next]);
}
const viewFromHash=()=>({'#send':'send','#historySection':'history','#network':'devices'}[location.hash]||'home');
setMobileView(viewFromHash());
window.addEventListener('hashchange',()=>setMobileView(viewFromHash()));

if(mobilePaged){
  document.body.classList.add('mobile-paged');
  $('mobileNav').addEventListener('click',event=>{const button=event.target.closest('button[data-view]');if(button)setMobileView(button.dataset.view)});
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href^="#"]');if(!link)return;
    if(link.classList.contains('skip-link')){event.preventDefault();$('top').focus();return}
    const views={'#top':'home','#send':'send','#historySection':'history','#network':'devices'};
    if(views[link.getAttribute('href')]){event.preventDefault();setMobileView(views[link.getAttribute('href')])}
  });
}

function toast(message,error=false){const node=$('toast');node.textContent=message;node.className=`show${error?' error':''}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.className='',3000)}
function showReceiveAlert(title,detail){
  let node=$('receiveAlert');if(!node){node=document.createElement('aside');node.id='receiveAlert';node.setAttribute('role','alertdialog');node.setAttribute('aria-live','assertive');document.body.append(node)}
  node.replaceChildren();const mark=document.createElement('span');mark.className='receive-alert-mark';mark.textContent='↓';const body=document.createElement('div');body.className='receive-alert-body';const heading=document.createElement('b');heading.textContent=title;const copy=document.createElement('span');copy.textContent=detail||'有新的传输内容';body.append(heading,copy);const close=document.createElement('button');close.type='button';close.setAttribute('aria-label','关闭接收提示');close.textContent='×';close.onclick=()=>node.classList.remove('show');node.append(mark,body,close);requestAnimationFrame(()=>node.classList.add('show'));clearTimeout(showReceiveAlert.timer);showReceiveAlert.timer=setTimeout(()=>node.classList.remove('show'),8000);
}
function announceIncoming(title,detail){playSound('connect');showReceiveAlert(title,detail);toast(detail?`${title} · ${detail}`:title)}
window.LocalLinkApp={notifyReceived:(title,detail)=>{announceIncoming(title||'收到新内容',detail||'');setTimeout(()=>refresh(),120)}};
async function request(path,options={}){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);try{const response=await fetch(apiUrl(path),{...options,signal:controller.signal,headers:{'X-LocalLink-Code':state.code,...(options.headers||{})}});let body={};try{body=await response.json()}catch{}if(!response.ok){const error=new Error(body.error||`请求失败 (${response.status})`);error.status=response.status;throw error}return body}finally{clearTimeout(timeout)}}
function showPair(){$('pairPanel').classList.remove('hidden');$('app').classList.add('hidden');$('connection').className='connection offline';$('connection').innerHTML='<i></i><b>等待配对</b>'}
function showApp(){$('pairPanel').classList.add('hidden');$('app').classList.remove('hidden');$('connection').className='connection online';$('connection').innerHTML='<i></i><b>服务在线</b>'}
function currentDevice(){if(!state.status)return null;return{id:state.status.device_id||`${state.status.ip}:${state.status.port}`,name:state.status.device,url:state.status.share_url,code:state.status.pairing_code,last_seen:Date.now()}}
function saveTrusted(){localStorage.setItem('locallink-trusted',JSON.stringify(state.trusted.slice(0,20)));renderTrusted()}
function isTrusted(){const device=currentDevice();return !!device&&state.trusted.some(item=>item.id===device.id)}
function toggleTrust(){const device=currentDevice();if(!device)return;state.trusted=isTrusted()?state.trusted.filter(item=>item.id!==device.id):[device,...state.trusted.filter(item=>item.id!==device.id)];saveTrusted();updateTrustButton();toast(isTrusted()?'已加入可信设备':'已取消信任')}
function updateTrustButton(){$('trustButton').textContent=isTrusted()?'已信任':'信任设备'}
function resolvedTrustedUrl(item){return window.LocalLinkConnection?.resolveTrustedUrl(item,state.status?.peers||[])||item.url}
function refreshTrustedAddresses(){let changed=false;state.trusted=state.trusted.map(item=>{const url=resolvedTrustedUrl(item);if(url===item.url)return item;changed=true;return{...item,url,last_seen:Date.now()}});if(changed)localStorage.setItem('locallink-trusted',JSON.stringify(state.trusted.slice(0,20)))}
function renderTrusted(){$('trustedDevices').innerHTML=state.trusted.length?state.trusted.map((item,index)=>`<div class="peer"><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(new URL(resolvedTrustedUrl(item)).host)} · 已保存直连</span></div><button type="button" data-trusted-open="${index}">连接</button><button type="button" data-trusted-remove="${index}">移除</button></div>`).join(''):'<div class="empty"><b>暂无已保存的直连设备</b><span>跨 Wi-Fi 连接一次并信任后，会保留在这里。</span></div>'}
function openModal(title,content){
  if($('modal').classList.contains('hidden'))modalReturnFocus=document.activeElement;
  previewItem.token=null;
  modalBackground=[document.querySelector('.topbar'),$('pairPanel'),$('app'),document.querySelector('footer')].filter(Boolean);
  modalBackground.forEach(node=>node.inert=true);
  document.body.classList.add('modal-open');
  $('modalTitle').textContent=title;$('modalBody').innerHTML=content;$('modal').classList.remove('hidden');$('modalClose').focus();
}
function closeModal(){
  if($('modal').classList.contains('hidden'))return;
  $('modal').classList.add('hidden');$('modalBody').innerHTML='';modalBackground.forEach(node=>node.inert=false);modalBackground=[];
  document.body.classList.remove('modal-open');
  if(modalReturnFocus?.isConnected)modalReturnFocus.focus();modalReturnFocus=null;
}
function copied(ok,label){if(ok)toast(`${label}已复制`);else toast('无法访问系统剪贴板，请长按或手动复制。',true)}
function showQr(){if(!state.status||typeof QRCode==='undefined')return;openModal('扫码连接',`<div class="qr-wrap"><div id="qrCanvas"></div><p>${escapeHtml(state.status.share_url)}</p><button id="copyQrLink" class="primary" type="button">复制连接地址</button></div>`);new QRCode($('qrCanvas'),{text:state.status.share_url,width:240,height:240,colorDark:'#16181d',colorLight:'#ffffff',correctLevel:QRCode.CorrectLevel.M});$('copyQrLink').onclick=async()=>copied(await copyText(state.status.share_url),'连接地址')}
function appendLinkedText(container,value){
  const text=String(value||''),pattern=/https?:\/\/[^\s<]+/gi;let last=0,match;
  while((match=pattern.exec(text))){container.append(document.createTextNode(text.slice(last,match.index)));const link=document.createElement('a');link.href=match[0];link.textContent=match[0];link.target='_blank';link.rel='noopener noreferrer';container.append(link);last=pattern.lastIndex}
  container.append(document.createTextNode(text.slice(last)));
}
function openTextReader(item){
  openModal('文本内容','');const reader=document.createElement('article');reader.className='text-reader';
  const meta=document.createElement('div');meta.className='text-reader-meta';meta.textContent=`${item.sender||'未知设备'} → ${item.receiver||'LocalLink'} · ${formatDate(item.created_at)}`;
  const tools=document.createElement('div');tools.className='text-reader-tools';const copy=document.createElement('button');copy.type='button';copy.textContent='复制全文';copy.onclick=async()=>copied(await copyText(item.text),'文本');const save=document.createElement('button');save.type='button';save.textContent='保存 TXT';save.onclick=()=>{const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([item.text],{type:'text/plain;charset=utf-8'}));link.download=`LocalLink-${item.id.slice(0,8)}.txt`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)};tools.append(copy,save);
  const content=document.createElement('pre');appendLinkedText(content,item.text);reader.append(meta,tools,content);$('modalBody').append(reader);
}
async function previewItem(item){
  if(item.kind==='text'){openTextReader(item);return}
  const view=LocalLinkUI.historyItem(item),url=LocalLinkUI.previewUrl(view,state.code),safe=escapeHtml(item.name),category=item.category||'';
  const title=item.name||'文件预览';
  if(category==='text'){
    openModal(title,'<p role="status">正在读取文件…</p>');
    const token=Symbol();previewItem.token=token;
    try{const response=await fetch(url);if(!response.ok)throw new Error('文件暂时无法读取');const value=await response.text();if(previewItem.token!==token||$('modal').classList.contains('hidden')||$('modalTitle').textContent!==title)return;$('modalBody').innerHTML='';const pre=document.createElement('pre');pre.textContent=value;$('modalBody').append(pre)}catch(error){if(previewItem.token===token&&!$('modal').classList.contains('hidden'))$('modalBody').textContent=error.message}return;
  }
  if(category==='image')openModal(title,`<img src="${url}" alt="${safe}">`);
  else if(category==='video')openModal(title,`<video src="${url}" controls playsinline></video>`);
  else if(category==='audio')openModal(title,`<audio src="${url}" controls></audio>`);
  else if(['pdf','document','spreadsheet','presentation'].includes(category))openModal(title,`<p class="preview-note">若设备不支持内嵌预览，可保存文件后用系统应用打开。</p><iframe src="${url}" title="${safe}" sandbox></iframe>`);
  else openModal(title,'<div class="preview-unavailable">此类型暂不支持预览，请保存后打开。</div>');
  const fallback=document.createElement('button');fallback.className='secondary';fallback.textContent='保存文件';fallback.onclick=()=>downloadFile(item.id,item.name);$('modalBody').append(fallback);
  $('modalBody').querySelectorAll('img,video,audio').forEach(media=>media.addEventListener('error',()=>{media.replaceWith(Object.assign(document.createElement('p'),{textContent:'无法预览此文件，请保存后使用系统应用打开。'}))},{once:true}));
}

let refreshing=false;
function detectIncomingRecords(data){
  const host=String(data.device_id||`${data.ip}:${data.port}`),records=data.history||[],ids=new Set(records.map(item=>String(item.id||'')).filter(Boolean));
  if(state.historyHost!==host){state.historyHost=host;state.knownRecordIds=ids;return}
  const fresh=records.filter(item=>item.id&&!state.knownRecordIds.has(String(item.id)));
  state.knownRecordIds=ids;
  if(!fresh.length)return;
  const item=fresh.sort((a,b)=>(b.created_at||0)-(a.created_at||0))[0];
  announceIncoming(item.kind==='text'?'收到新文字':'收到新文件',item.kind==='text'?(item.sender||'未知设备'):`${item.sender||'未知设备'} · ${item.name||'文件'}`);
}
async function refresh(){
  if(refreshing)return;refreshing=true;
  try{
    const data=await request('/api/status');state.status=data;refreshTrustedAddresses();localStorage.setItem('locallink-code',state.code);showApp();
    $('connectionNotice').classList.add('hidden');
    data.history=Array.isArray(data.history)?data.history:[];data.peers=Array.isArray(data.peers)?data.peers:[];detectIncomingRecords(data);
    $('historyOwner').textContent=`保存在「${data.device}」的内容 · ${data.ip}:${data.port}`;
    $('sendDestination').textContent=`接收主机：${data.device} · ${data.ip}:${data.port}`;
    $('deviceName').textContent=data.device;$('deviceAddress').textContent=`${data.ip}:${data.port}`;$('pairingCode').textContent=data.pairing_code;updateTrustButton();renderTrusted();
    $('networkIp').textContent=data.ip;$('peerCount').textContent=`${data.peers.length} 台`;
    $('statItems').textContent=data.storage?.items??data.history.length;$('statFiles').textContent=data.storage?.files??0;$('statStorage').textContent=data.storage?.bytes_human??'0 B';$('statPeers').textContent=data.peers.length;
    renderNetwork(data.network||{});renderPeers(data.peers);renderHistory();
  }catch(error){if(error.status===401||!state.status)showPair();else{$('connection').className='connection offline';$('connection').innerHTML='<i></i><b>连接中断</b>';$('connectionNotice').textContent='主机暂未响应，当前显示上次记录。连接恢复后会自动更新。';$('connectionNotice').classList.remove('hidden')}}finally{refreshing=false}
}
function renderNetwork(network){const blocked=network.lan_state==='blocked',ok=network.lan_state==='ok';$('lanState').textContent=blocked?'受 VPN 限制':ok?'连接正常':'服务已监听';$('vpnState').textContent=network.vpn_detected?'已开启':'未检测到';const firewall={configured:'已允许',approval_requested:'等待授权',blocked:'需要手动允许',not_checked:'未检测',not_required:'无需配置'};$('firewallState').textContent=firewall[network.firewall]||'未检测';$('networkHint').textContent=network.firewall==='approval_requested'?'请完成 Windows 管理员授权，允许手机访问 53317 端口。':network.message||'自动发现仅限同一 Wi-Fi 广播域；不同 Wi-Fi 但可互访时，请用地址或二维码直连并保存为可信设备。'}
function renderPeers(peers){$('peers').innerHTML=peers.length?peers.map((peer,index)=>`<div class="peer"><div><strong>${escapeHtml(peer.name)}</strong><span>${escapeHtml(peer.ip)}:${peer.port} · 自动发现</span></div><button type="button" data-peer-open="${index}">连接</button></div>`).join(''):'<div class="empty"><b>未发现同一广播域的设备</b><span>不同 Wi-Fi 的可达设备不会自动出现；请使用下方已保存设备或手动地址连接。</span></div>'}
const typeNames={text:'文字',image:'图片',video:'视频',audio:'音频',pdf:'PDF',document:'文档',spreadsheet:'表格',presentation:'演示文稿',archive:'压缩文件',package:'安装包',apk:'安装包',file:'文件'};
const icons={text:'M5 5h14M12 5v14M8 19h8',image:'M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M15 8h.01',file:'M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6',arrow:'M4 12h16m-5-5 5 5-5 5',folder:'M3 7h7l2 2h9v11H3z'};
const icon=name=>`<svg aria-hidden="true" viewBox="0 0 24 24"><path d="${icons[name]||icons.file}"/></svg>`;
let historySignature='';
function dayLabel(value){if(!value)return '日期未知';const date=new Date(value*1000),today=new Date(),yesterday=new Date();yesterday.setDate(today.getDate()-1);return date.toDateString()===today.toDateString()?'今天':date.toDateString()===yesterday.toDateString()?'昨天':date.toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})}
function filteredItems(){return LocalLinkUI.selectHistory(state.status?.history,state)}
function renderHistory(){
  const result=filteredItems();state.page=result.page;
  const signature=JSON.stringify([result,state.filter,state.query,state.sort]);if(signature===historySignature)return;historySignature=signature;
  const focused=document.activeElement?.closest('#history button');const restore=focused?{id:focused.dataset.id,action:focused.dataset.action}:null;
  $('historyCount').textContent=`${result.total} 条记录${result.total!==result.all?` / 共 ${result.all} 条`:''}`;
  $('resetHistory').classList.toggle('hidden',state.filter==='all'&&!state.query&&state.sort==='newest');
  $('historyPage').textContent=`第 ${result.page} / ${result.pages} 页`;
  $('historyPrevious').disabled=result.page<=1;$('historyNext').disabled=result.page>=result.pages;$('clearButton').disabled=!result.all;
  document.querySelectorAll('[data-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.filter===state.filter)));
  if(!result.items.length){$('history').innerHTML=`<div class="empty">${icon('folder')}<b>${result.all?'没有找到匹配的记录':'这里等待你的第一份内容'}</b><span>${result.all?'试试其他关键词，或重置筛选条件。':'发送文字或文件后，会保存在这台主机上。'}</span>${result.all?'<button class="secondary" data-reset-history>重置筛选</button>':'<a href="#send" class="primary">发送内容</a>'}</div>`;return}
  let previousDay='';
  $('history').innerHTML=result.items.map(item=>{
    const isText=item.kind==='text',id=escapeHtml(item.id),receiver=escapeHtml(item.receiver||state.status.device||'接收主机');
    const day=state.sort==='largest'?'按文件大小':dayLabel(item.created_at),heading=day!==previousDay?`<h3 class="day-heading">${day}</h3>`:'';previousDay=day;
    const primary=isText?'read':item.actions.includes('preview_inline')?'preview_inline':item.actions.includes('preview_convert')?'preview_convert':'details';
    const primaryLabel=isText?'阅读全文':primary==='details'?'查看详情':'预览';
    const secondary=isText?'copy':item.actions.includes('download')?'download':'details';
    const thumb=item.category==='image'&&item.available?`<img src="${LocalLinkUI.previewUrl(item,state.code)}" loading="lazy" alt="" class="record-thumbnail">`:icon(isText?'text':'file');
    return `${heading}<article class="history-item ${isText?'message-record':'file-record'}"><div class="record-icon type-${escapeHtml(item.displayKind)}">${thumb}</div><div class="record-content"><div class="record-label"><span>${!isText&&item.displayKind==='text'?'文本文件':typeNames[item.displayKind]||'文件'}</span><time>${formatDate(item.created_at)}</time></div>${isText?`<p class="text-summary">${escapeHtml(item.summary.slice(0,1200))||'（空文本）'}</p>`:`<h4 class="file-name">${escapeHtml(item.name)}</h4>`}<div class="record-route"><span title="发送端">来自 <b>${escapeHtml(item.sender)}</b></span>${icon('arrow')}<span title="接收端">送达 <b>${receiver}</b></span></div><div class="record-meta">${isText?`${item.text.length.toLocaleString()} 字符` :escapeHtml(item.size_human)}${!item.available?'<span class="missing-state">文件已移动或删除</span>':''}</div></div><div class="actions"><button data-id="${id}" data-action="${primary}">${primaryLabel}</button>${secondary!==primary?`<button data-id="${id}" data-action="${secondary}">${isText?'复制':secondary==='download'?'保存':'详情'}</button>`:''}${primary!=='details'&&secondary!=='details'?`<button class="record-more" data-id="${id}" data-action="details" aria-label="查看记录详情和更多操作">详情</button>`:''}</div></article>`;
  }).join('');
  if(restore){const target=[...$('history').querySelectorAll('button')].find(button=>button.dataset.id===restore.id&&button.dataset.action===restore.action);target?.focus({preventScroll:true})}
}
function resetHistory(){state.query='';state.filter='all';state.sort='newest';state.page=1;$('historySearch').value='';$('historySort').value='newest';renderHistory()}
function showDetails(raw){
  const item=LocalLinkUI.historyItem(raw),labels={read:'阅读全文',copy:'复制文字',preview_inline:'预览',preview_convert:'预览 PDF',open_external:'用应用打开',install:'安装',download:'保存文件',delete:'删除内容'};
  openModal(item.kind==='text'?'文字详情':item.name,`<dl class="record-details"><div><dt>发送端</dt><dd>${escapeHtml(item.sender)}</dd></div><div><dt>接收端</dt><dd>${escapeHtml(item.receiver||state.status.device)}</dd></div><div><dt>时间</dt><dd>${formatDate(item.created_at)}</dd></div><div><dt>大小</dt><dd>${escapeHtml(item.size_human)}</dd></div><div><dt>可用状态</dt><dd>${item.available?'内容可用':'文件已移动或删除，仅保留记录'}</dd></div>${item.sha256?`<div><dt>SHA-256</dt><dd class="checksum">${escapeHtml(item.sha256)}</dd></div>`:''}</dl><p class="preview-note">删除会移除此主机上的记录和对应文件，无法撤销。</p><div class="detail-actions">${item.actions.map(action=>`<button class="secondary ${action==='delete'?'danger-action':''}" data-action="${action}" data-id="${escapeHtml(item.id)}">${labels[action]||action}</button>`).join('')}</div>`);
}
async function recordAction(event){
  const button=event.target.closest('button[data-action]');if(!button||button.disabled)return;
  const {action,id}=button.dataset,raw=state.status?.history.find(item=>String(item.id)===id);if(!raw){toast('记录已更新，请刷新后重试',true);return}
  const item=LocalLinkUI.historyItem(raw);
  try{
    if(action==='details'){showDetails(item);return}
    if(['read','preview_inline','preview_convert'].includes(action)){await previewItem(item);return}
    if(action==='copy'){copied(await copyText(item.text),'文本');return}
    if(action==='download'){downloadFile(id,item.name);return}
    if(action==='open_external'||action==='install'){if(window.LocalLinkNative?.openRecord)window.LocalLinkNative.openRecord(id,action);else downloadFile(id,item.name);return}
    if(action==='delete'){
      if(!confirm(`删除${item.kind==='text'?'这条文字':`「${item.name}」`}？\n将删除「${item.receiver||state.status.device}」上的记录和对应文件，无法撤销。`))return;
      button.disabled=true;await request(`/api/items/${encodeURIComponent(id)}`,{method:'DELETE'});closeModal();state.status.history=state.status.history.filter(record=>String(record.id)!==id);renderHistory();toast('内容已删除');await refresh();
    }
  }catch(error){toast(error.message||'操作失败，请重试',true)}finally{button.disabled=false}
}
async function copyText(value){
  const text=String(value??'');if(!text)return false;
  const timed=promise=>Promise.race([Promise.resolve(promise),new Promise(resolve=>setTimeout(()=>resolve(false),1200))]);
  try{if(window.LocalLinkNative?.copyText&&await timed(window.LocalLinkNative.copyText(text)))return true}catch{}
  try{if(navigator.clipboard?.writeText&&await timed(navigator.clipboard.writeText(text)))return true}catch{}
  const area=document.createElement('textarea');area.value=text;area.readOnly=true;area.setAttribute('aria-hidden','true');area.style.cssText='position:fixed;left:-9999px;top:0;opacity:0;pointer-events:none';document.body.append(area);area.focus();area.select();area.setSelectionRange(0,text.length);
  let copied=false;try{copied=document.execCommand('copy')}catch{}finally{area.remove()}return copied;
}
function downloadFile(id,name){const link=document.createElement('a');link.href=apiUrl(`/api/download/${id}`);link.download=name||'download';link.style.display='none';document.body.append(link);link.click();setTimeout(()=>link.remove(),1000);toast('已开始下载，页面将保持不变')}

$('pairForm').addEventListener('submit',event=>{event.preventDefault();ensureAudio();state.code=$('pairCode').value.trim();refresh()});
$('copyLinkButton').addEventListener('click',async()=>{if(!state.status)return;copied(await copyText(state.status.share_url),'设备访问地址')});
$('qrButton').addEventListener('click',showQr);$('trustButton').addEventListener('click',toggleTrust);$('modalClose').addEventListener('click',closeModal);$('modal').addEventListener('click',event=>{if(event.target===$('modal'))closeModal()});document.addEventListener('keydown',event=>{if(event.key==='Escape')closeModal();if(event.key==='Tab'&&!$('modal').classList.contains('hidden')){const focusable=[...$('modal').querySelectorAll('button,a[href],input,select,textarea,iframe,audio[controls],video[controls],[tabindex]:not([tabindex="-1"])')].filter(node=>!node.disabled);if(!focusable.length)return;const first=focusable[0],last=focusable[focusable.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}}});
$('soundButton').addEventListener('click',()=>{state.sound=!state.sound;localStorage.setItem('locallink-sound',state.sound?'on':'off');updateSoundButton();if(state.sound)playSound('connect')});updateSoundButton();
$('trustedDevices').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;const open=button.dataset.trustedOpen,remove=button.dataset.trustedRemove;if(open!==undefined)location.href=resolvedTrustedUrl(state.trusted[Number(open)]);if(remove!==undefined){state.trusted.splice(Number(remove),1);saveTrusted();toast('已移除可信设备')}});
$('peers').addEventListener('click',event=>{const button=event.target.closest('button[data-peer-open]');if(!button)return;const peer=state.status?.peers?.[Number(button.dataset.peerOpen)];if(!peer)return;const address=`http://${peer.ip}:${peer.port}/?client=${encodeURIComponent(senderName())}`;location.assign(address)});
$('textInput').addEventListener('input',event=>$('charCount').textContent=`${event.target.value.length} / 262144`);
$('textForm').addEventListener('submit',async event=>{event.preventDefault();ensureAudio();const button=event.submitter;button.disabled=true;try{await request('/api/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('textInput').value,sender:senderName()})});$('textInput').value='';$('charCount').textContent='0 / 262144';playSound('send');toast('文字发送成功');await refresh()}catch(error){playSound('error');toast(error.message,true)}finally{button.disabled=false}});
$('refreshButton').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;button.textContent='刷新中…';try{await refresh()}finally{button.disabled=false;button.textContent='刷新'}});
$('clearButton').addEventListener('click',async()=>{if(!state.status?.history?.length){toast('当前没有传输记录');return}if(!confirm('清空全部传输记录和本地接收文件？此操作无法撤销。'))return;try{const result=await request('/api/items',{method:'DELETE'});toast(`已清空 ${result.deleted||0} 条记录`);await refresh()}catch(error){toast(error.message,true)}});
$('scanButton').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;try{await request('/api/scan',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}});toast('正在扫描当前 Wi-Fi 网段');setTimeout(refresh,1800)}catch(error){toast(error.message,true)}finally{setTimeout(()=>button.disabled=false,1800)}});
$('historySearch').addEventListener('input',event=>{state.query=event.target.value;state.page=1;renderHistory()});
$('historySort').addEventListener('change',event=>{state.sort=event.target.value;state.page=1;renderHistory()});
$('historyCategories').addEventListener('click',event=>{const button=event.target.closest('[data-filter]');if(button){state.filter=button.dataset.filter;state.page=1;renderHistory()}});
$('resetHistory').addEventListener('click',resetHistory);
$('historyPrevious').addEventListener('click',()=>{state.page--;renderHistory();$('historySection').scrollIntoView({block:'start'})});
$('historyNext').addEventListener('click',()=>{state.page++;renderHistory();$('historySection').scrollIntoView({block:'start'})});
$('history').addEventListener('click',event=>{if(event.target.closest('[data-reset-history]'))resetHistory();else recordAction(event)});
$('modalBody').addEventListener('click',recordAction);

async function sha256(file){if(file.size>128*1024*1024)return '';try{const data=await file.arrayBuffer(),digest=await crypto.subtle.digest('SHA-256',data);return [...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')}catch{return ''}}
async function uploadFile(file){
  const row=document.createElement('div');row.className='upload-item';row.innerHTML=`<div class="upload-meta"><span>${escapeHtml(file.name)}</span><b>准备中</b></div><div class="bar"><i></i></div>`;$('uploadQueue').prepend(row);
  const label=row.querySelector('b'),bar=row.querySelector('i');
  try{const digest=await sha256(file);label.textContent='上传中';await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',apiUrl('/api/upload'));xhr.setRequestHeader('X-LocalLink-Code',state.code);xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));xhr.setRequestHeader('X-Sender',encodeURIComponent(senderName()));if(digest)xhr.setRequestHeader('X-SHA256',digest);xhr.upload.onprogress=e=>{if(e.lengthComputable)bar.style.width=`${e.loaded/e.total*100}%`};xhr.onload=()=>xhr.status<300?resolve():reject(new Error('上传失败'));xhr.onerror=()=>reject(new Error('网络中断'));xhr.send(file)});label.textContent='完成';bar.style.width='100%';playSound('send');toast(`${file.name} 发送成功`)}catch(error){label.textContent='失败';playSound('error');toast(`${file.name}: ${error.message}`,true)}
}
async function uploadFiles(files){if(!files.length)return;ensureAudio();for(const file of files)await uploadFile(file);$('fileInput').value='';await refresh()}
$('fileInput').addEventListener('change',event=>uploadFiles([...event.target.files]));
const drop=$('dropZone');['dragenter','dragover'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',event=>uploadFiles([...event.dataTransfer.files]));

refresh();setInterval(()=>{if(!document.hidden&&state.code)refresh()},5000);
