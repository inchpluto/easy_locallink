(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LocalLinkUI = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function unique(values) {
    return [...new Set(values.filter(Boolean))];
  }

  function historyItem(item) {
    const available = item.kind === 'text' || item.available !== false;
    let actions;
    if (item.kind === 'text') {
      actions = item.actions?.includes('read') ? item.actions : ['read', 'copy'];
    } else {
      actions = available ? (item.actions || ['download']) : [];
    }
    return {
      ...item,
      displayKind: item.kind === 'text' ? 'text' : (item.category || 'file'),
      summary: item.kind === 'text' ? String(item.text || '') : String(item.name || ''),
      actions: unique([...actions, 'delete']),
    };
  }

  function previewUrl(item, code) {
    const format = item.actions?.includes('preview_convert') ? '?format=pdf' : '';
    return `/api/preview/${encodeURIComponent(item.id)}${format}${format ? '&' : '?'}code=${encodeURIComponent(code)}`;
  }

  return { historyItem, previewUrl };
});
