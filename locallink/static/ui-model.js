(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LocalLinkUI = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function unique(values) {
    return [...new Set(values.filter(Boolean))];
  }

  function historyItem(item) {
    item = item && typeof item === 'object' ? item : {};
    const available = item.kind === 'text' || item.available !== false;
    const suppliedActions = Array.isArray(item.actions) ? item.actions.filter(action => typeof action === 'string') : null;
    let actions;
    if (item.kind === 'text') {
      actions = suppliedActions?.includes('read') ? suppliedActions : ['read', 'copy'];
    } else {
      actions = available ? (suppliedActions || ['download']) : [];
    }
    return {
      ...item,
      id: String(item.id || ''),
      name: String(item.name || '未命名文件'),
      text: String(item.text || ''),
      sha256: String(item.sha256 || ''),
      sender: String(item.sender || '未知设备'),
      receiver: String(item.receiver || ''),
      created_at: Number.isFinite(Number(item.created_at)) ? Number(item.created_at) : 0,
      size: Math.max(0, Number(item.size) || 0),
      size_human: item.size_human || formatSize(item.size),
      available,
      displayKind: item.kind === 'text' ? 'text' : (item.category || 'file'),
      summary: item.kind === 'text' ? String(item.text || '') : String(item.name || ''),
      actions: unique([...actions, 'delete']),
    };
  }

  function formatSize(value) {
    let size = Math.max(0, Number(value) || 0), index = 0;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    while (size >= 1024 && index < units.length - 1) { size /= 1024; index++; }
    return `${index ? size.toFixed(1) : size} ${units[index]}`;
  }

  function selectHistory(records, {query='', filter='all', sort='newest', page=1, pageSize=20}={}) {
    const normalized = (Array.isArray(records) ? records : []).filter(item => item && item.id).map(historyItem);
    const q = String(query).trim().toLocaleLowerCase();
    const documents = ['document','spreadsheet','presentation','pdf'];
    const items = normalized.filter(item => {
      const matches = filter === 'all' || (filter === 'file' && item.kind !== 'text') ||
        (filter === 'text' && item.kind === 'text') || (filter === 'documents' && documents.includes(item.category)) ||
        (filter === 'missing' && !item.available) || (filter === 'image' && item.category === 'image');
      return matches && (!q || [item.name,item.text,item.sender,item.receiver].join(' ').toLocaleLowerCase().includes(q));
    }).sort((a,b) => (sort === 'oldest' ? a.created_at-b.created_at : sort === 'largest' ? b.size-a.size : b.created_at-a.created_at) || a.id.localeCompare(b.id));
    const limit = Math.max(1, Math.min(100, Number(pageSize) || 20));
    const pages = Math.max(1, Math.ceil(items.length / limit));
    const current = Math.max(1, Math.min(pages, Number(page) || 1));
    return {items:items.slice((current-1)*limit,current*limit), total:items.length, all:normalized.length, page:current, pages};
  }

  function previewUrl(item, code) {
    const format = item.actions?.includes('preview_convert') ? '?format=pdf' : '';
    return `/api/preview/${encodeURIComponent(item.id)}${format}${format ? '&' : '?'}code=${encodeURIComponent(code)}`;
  }

  return { historyItem, previewUrl, selectHistory, formatSize };
});
