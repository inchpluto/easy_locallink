const state={code:new URLSearchParams(location.search).get('code')||localStorage.getItem('locallink-code')||'',status:null,query:'',filter:'all',trusted:JSON.parse(localStorage.getItem('locallink-trusted')||'[]')};
const $=id=>document.getElementById(id);
const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const formatDate=value=>new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value*1000));
const apiUrl=path=>`${path}${path.includes('?')?'&':'?'}code=${encodeURIComponent(state.code)}`;
const isMobile=()=>/Android|Mobile/i.test(navigator.userAgent);
const senderName=()=>new URLSearchParams(location.search).get('client')||(isMobile()?'手机端':'电脑端');
let toastTimer;

const mobilePaged=isMobile()||window.matchMedia('(max-width:600px)').matches;
function setMobileView(view){
  if(!mobilePaged)return;
  const allowed=['home','send','history','devices'];
  const next=allowed.includes(view)?view:'home';
  $('app').dataset.view=next;
  document.querySelectorAll('#mobileNav button').forEach(button=>{
    const active=button.dataset.view===next;
    button.classList.toggle('active',active);
    active?button.setAttribute('aria-current','page'):button.removeAttribute('aria-current');
  });
  window.scrollTo({top:0,behavior:'smooth'});
}

if(mobilePaged){
  document.body.classList.add('mobile-paged');
  $('app').dataset.view='home';
  $('mobileNav').addEventListener('click',event=>{const button=event.target.closest('button[data-view]');if(button)setMobileView(button.dataset.view)});
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href^="#"]');if(!link)return;
    const views={'#top':'home','#send':'send','#historySection':'history','#network':'devices'};
    if(views[link.getAttribute('href')]){event.preventDefault();setMobileView(views[link.getAttribute('href')])}
  });
}

function toast(message,error=false){const node=$('toast');node.textContent=message;node.className=`show${error?' error':''}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.className='',3000)}
async function request(path,options={}){const response=await fetch(apiUrl(path),{...options,headers:{'X-LocalLink-Code':state.code,...(options.headers||{})}});let body={};try{body=await response.json()}catch{}if(!response.ok)throw new Error(body.error||`请求失败 (${response.status})`);return body}
function showPair(){$('pairPanel').classList.remove('hidden');$('app').classList.add('hidden');$('connection').className='connection offline';$('connection').innerHTML='<i></i><b>等待配对</b>'}
function showApp(){$('pairPanel').classList.add('hidden');$('app').classList.remove('hidden');$('connection').className='connection online';$('connection').innerHTML='<i></i><b>服务在线</b>'}
function currentDevice(){if(!state.status)return null;return{id:state.status.device_id||`${state.status.ip}:${state.status.port}`,name:state.status.device,url:state.status.share_url,code:state.status.pairing_code,last_seen:Date.now()}}
function saveTrusted(){localStorage.setItem('locallink-trusted',JSON.stringify(state.trusted.slice(0,20)));renderTrusted()}
function isTrusted(){const device=currentDevice();return !!device&&state.trusted.some(item=>item.id===device.id)}
function toggleTrust(){const device=currentDevice();if(!device)return;state.trusted=isTrusted()?state.trusted.filter(item=>item.id!==device.id):[device,...state.trusted.filter(item=>item.id!==device.id)];saveTrusted();updateTrustButton();toast(isTrusted()?'已加入可信设备':'已取消信任')}
function updateTrustButton(){$('trustButton').textContent=isTrusted()?'已信任':'信任设备'}
function renderTrusted(){$('trustedDevices').innerHTML=state.trusted.length?state.trusted.map((item,index)=>`<div class="peer"><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(new URL(item.url).host)}</span></div><button type="button" data-trusted-open="${index}">连接</button><button type="button" data-trusted-remove="${index}">移除</button></div>`).join(''):'<div class="empty"><b>暂无可信设备</b><span>连接后可在主页将设备加入信任列表</span></div>'}
function openModal(title,content){$('modalTitle').textContent=title;$('modalBody').innerHTML=content;$('modal').classList.remove('hidden')}
function closeModal(){$('modal').classList.add('hidden');$('modalBody').innerHTML=''}
function showQr(){if(!state.status||typeof QRCode==='undefined')return;openModal('扫码连接',`<div class="qr-wrap"><div id="qrCanvas"></div><p>${escapeHtml(state.status.share_url)}</p><button id="copyQrLink" class="primary" type="button">复制连接地址</button></div>`);new QRCode($('qrCanvas'),{text:state.status.share_url,width:240,height:240,colorDark:'#16181d',colorLight:'#ffffff',correctLevel:QRCode.CorrectLevel.M});$('copyQrLink').onclick=async()=>{await copyText(state.status.share_url);toast('连接地址已复制')}}
function appendLinkedText(container,value){
  const text=String(value||''),pattern=/https?:\/\/[^\s<]+/gi;let last=0,match;
  while((match=pattern.exec(text))){container.append(document.createTextNode(text.slice(last,match.index)));const link=document.createElement('a');link.href=match[0];link.textContent=match[0];link.target='_blank';link.rel='noopener noreferrer';container.append(link);last=pattern.lastIndex}
  container.append(document.createTextNode(text.slice(last)));
}
function openTextReader(item){
  openModal('文本内容','');const reader=document.createElement('article');reader.className='text-reader';
  const meta=document.createElement('div');meta.className='text-reader-meta';meta.textContent=`${item.sender||'未知设备'} → ${item.receiver||'LocalLink'} · ${formatDate(item.created_at)}`;
  const content=document.createElement('pre');appendLinkedText(content,item.text);reader.append(meta,content);$('modalBody').append(reader);
}
function previewItem(item){
  if(item.kind==='text'){openTextReader(item);return}
  const view=LocalLinkUI.historyItem(item),url=LocalLinkUI.previewUrl(view,state.code),safe=escapeHtml(item.name),category=item.category||'';
  if(category==='image')openModal(safe,`<img src="${url}" alt="${safe}">`);
  else if(category==='video')openModal(safe,`<video src="${url}" controls playsinline></video>`);
  else if(category==='audio')openModal(safe,`<audio src="${url}" controls></audio>`);
  else if(['pdf','text','document','spreadsheet','presentation'].includes(category))openModal(safe,`<iframe src="${url}" title="${safe}" sandbox></iframe>`);
  else openModal(safe,'<div class="preview-unavailable">此类型暂不支持预览，请下载后打开。</div>');
}

async function refresh(){
  try{
    const data=await request('/api/status');state.status=data;localStorage.setItem('locallink-code',state.code);showApp();
    $('deviceName').textContent=data.device;$('deviceAddress').textContent=`${data.ip}:${data.port}`;$('pairingCode').textContent=data.pairing_code;updateTrustButton();renderTrusted();
    $('networkIp').textContent=data.ip;$('peerCount').textContent=`${data.peers.length} 台`;
    $('statItems').textContent=data.storage?.items??data.history.length;$('statFiles').textContent=data.storage?.files??0;$('statStorage').textContent=data.storage?.bytes_human??'0 B';$('statPeers').textContent=data.peers.length;
    renderNetwork(data.network||{});renderPeers(data.peers);renderHistory();
  }catch(error){showPair();if(state.code)toast(error.message,true)}
}
function renderNetwork(network){const blocked=network.lan_state==='blocked',ok=network.lan_state==='ok';$('lanState').textContent=blocked?'受 VPN 限制':ok?'连接正常':'服务已监听';$('vpnState').textContent=network.vpn_detected?'已开启':'未检测到';const firewall={configured:'已允许',approval_requested:'等待授权',blocked:'需要手动允许',not_checked:'未检测',not_required:'无需配置'};$('firewallState').textContent=firewall[network.firewall]||'未检测';$('networkHint').textContent=network.firewall==='approval_requested'?'请完成 Windows 管理员授权，允许手机访问 53317 端口。':network.message||'服务已启动，请用上方地址连接。'}
function renderPeers(peers){$('peers').innerHTML=peers.length?peers.map(peer=>`<div class="peer"><strong>${escapeHtml(peer.name)}</strong><span>${escapeHtml(peer.ip)}:${peer.port}</span></div>`).join(''):'<div class="empty"><b>等待设备连接</b><span>手机打开 LocalLink 并连接当前主机</span></div>'}
function filteredItems(){const q=state.query.toLowerCase();return (state.status?.history||[]).filter(item=>(state.filter==='all'||item.kind===state.filter)&&(!q||`${item.name} ${item.sender} ${item.receiver} ${item.text}`.toLowerCase().includes(q)))}
function renderHistory(){
  const items=filteredItems().map(LocalLinkUI.historyItem);
  if(!items.length){$('history').innerHTML='<div class="empty"><b>暂无记录</b><span>没有符合条件的传输内容</span></div>';return}
  $('history').innerHTML=items.map(item=>{
    const isText=item.kind==='text',receiver=escapeHtml(item.receiver||state.status.device||'LocalLink 主机');
    const labels={read:'全文',copy:'复制',preview_inline:'预览',preview_convert:'PDF 预览',open_external:'打开',install:'安装',download:'下载',delete:'删除'};
    const actions=item.actions.map(action=>`<button type="button" class="${action==='delete'?'danger':''}" data-action="${action}" data-id="${item.id}" data-name="${escapeHtml(item.name||'')}">${labels[action]||action}</button>`).join('');
    const title=isText?`<strong class="text-summary">${escapeHtml(item.summary)}</strong><p>文本消息</p>`:`<strong class="file-name">${escapeHtml(item.name)}</strong><p>${escapeHtml(item.displayKind)}</p>`;
    return `<article class="history-item" data-id="${item.id}"><div class="payload"><span class="payload-icon">${isText?'TXT':'FILE'}</span><div class="payload-content">${title}</div></div><div class="route"><div class="route-device"><b>${escapeHtml(item.sender||'未知设备')}</b><small>发送端</small></div><span class="route-arrow">→</span><div class="route-device"><b>${receiver}</b><small>接收端</small></div></div><div class="meta">${formatDate(item.created_at)}<br>${item.size_human}${isText?'':` · ${item.sha256.slice(0,8)}`}</div><div class="actions">${actions}</div></article>`
  }).join('');
}
async function copyText(value){try{await navigator.clipboard.writeText(value)}catch{const area=document.createElement('textarea');area.value=value;area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();document.execCommand('copy');area.remove()}}
function downloadFile(id,name){const link=document.createElement('a');link.href=apiUrl(`/api/download/${id}`);link.download=name||'download';link.style.display='none';document.body.append(link);link.click();setTimeout(()=>link.remove(),1000);toast('已开始下载，页面将保持不变')}

$('pairForm').addEventListener('submit',event=>{event.preventDefault();state.code=$('pairCode').value.trim();refresh()});
$('copyLinkButton').addEventListener('click',async()=>{if(!state.status)return;await copyText(state.status.share_url);toast('设备访问地址已复制')});
$('qrButton').addEventListener('click',showQr);$('trustButton').addEventListener('click',toggleTrust);$('modalClose').addEventListener('click',closeModal);$('modal').addEventListener('click',event=>{if(event.target===$('modal'))closeModal()});document.addEventListener('keydown',event=>{if(event.key==='Escape')closeModal()});
$('trustedDevices').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;const open=button.dataset.trustedOpen,remove=button.dataset.trustedRemove;if(open!==undefined)location.href=state.trusted[Number(open)].url;if(remove!==undefined){state.trusted.splice(Number(remove),1);saveTrusted();toast('已移除可信设备')}});
$('textInput').addEventListener('input',event=>$('charCount').textContent=`${event.target.value.length} / 262144`);
$('textForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{await request('/api/text',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('textInput').value,sender:senderName()})});$('textInput').value='';$('charCount').textContent='0 / 262144';toast('文字发送成功');await refresh()}catch(error){toast(error.message,true)}finally{button.disabled=false}});
$('refreshButton').addEventListener('click',refresh);
$('clearButton').addEventListener('click',async()=>{if(!state.status?.history?.length){toast('当前没有传输记录');return}if(!confirm('清空全部传输记录和本地接收文件？此操作无法撤销。'))return;try{const result=await request('/api/items',{method:'DELETE'});toast(`已清空 ${result.deleted||0} 条记录`);await refresh()}catch(error){toast(error.message,true)}});
$('scanButton').addEventListener('click',async event=>{event.currentTarget.disabled=true;try{await request('/api/scan',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}});toast('正在扫描当前局域网');setTimeout(refresh,1800)}catch(error){toast(error.message,true)}finally{setTimeout(()=>event.currentTarget.disabled=false,1800)}});
$('historySearch').addEventListener('input',event=>{state.query=event.target.value;renderHistory()});
$('historyFilter').addEventListener('change',event=>{state.filter=event.target.value;renderHistory()});
$('history').addEventListener('click',async event=>{const button=event.target.closest('button[data-action]');if(!button)return;const {action,id,name}=button.dataset,item=state.status.history.find(x=>x.id===id);if(!item)return;if(action==='read'||action==='preview_inline'||action==='preview_convert')previewItem(item);if(action==='copy'){await copyText(item.text);toast('文本已复制')}if(action==='download')downloadFile(id,name);if(action==='open_external'||action==='install'){if(window.LocalLinkNative?.openRecord)window.LocalLinkNative.openRecord(id,action);else downloadFile(id,name)}if(action==='delete'&&confirm('删除这条记录及对应文件？')){try{await request(`/api/items/${id}`,{method:'DELETE'});toast('记录已删除');await refresh()}catch(error){toast(error.message,true)}}});

async function sha256(file){if(file.size>128*1024*1024)return '';try{const data=await file.arrayBuffer(),digest=await crypto.subtle.digest('SHA-256',data);return [...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')}catch{return ''}}
async function uploadFile(file){
  const row=document.createElement('div');row.className='upload-item';row.innerHTML=`<div class="upload-meta"><span>${escapeHtml(file.name)}</span><b>准备中</b></div><div class="bar"><i></i></div>`;$('uploadQueue').prepend(row);
  const label=row.querySelector('b'),bar=row.querySelector('i');
  try{const digest=await sha256(file);label.textContent='上传中';await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',apiUrl('/api/upload'));xhr.setRequestHeader('X-LocalLink-Code',state.code);xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));xhr.setRequestHeader('X-Sender',encodeURIComponent(senderName()));if(digest)xhr.setRequestHeader('X-SHA256',digest);xhr.upload.onprogress=e=>{if(e.lengthComputable)bar.style.width=`${e.loaded/e.total*100}%`};xhr.onload=()=>xhr.status<300?resolve():reject(new Error('上传失败'));xhr.onerror=()=>reject(new Error('网络中断'));xhr.send(file)});label.textContent='完成';bar.style.width='100%';toast(`${file.name} 发送成功`)}catch(error){label.textContent='失败';toast(`${file.name}: ${error.message}`,true)}
}
async function uploadFiles(files){if(!files.length)return;for(const file of files)await uploadFile(file);$('fileInput').value='';await refresh()}
$('fileInput').addEventListener('change',event=>uploadFiles([...event.target.files]));
const drop=$('dropZone');['dragenter','dragover'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(name=>drop.addEventListener(name,event=>{event.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',event=>uploadFiles([...event.dataTransfer.files]));

refresh();setInterval(()=>{if(!document.hidden&&state.code)refresh()},5000);
