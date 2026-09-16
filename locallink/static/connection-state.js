(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LocalLinkConnection = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const states = Object.freeze(['idle','probing','authenticating','ready','retrust_required','failed']);

  function classify(probeResult, statusResult, trustedDevice) {
    if (!probeResult?.ok) return {state:'failed', error:'OFFLINE'};
    if (probeResult.service !== 'locallink') return {state:'failed', error:'NOT_LOCALLINK'};
    if (!statusResult?.ok) {
      return {state:'failed', error:statusResult?.status === 401 ? 'PAIRING_REJECTED' : 'AUTH_FAILED'};
    }
    if (trustedDevice?.id && probeResult.id && trustedDevice.id !== probeResult.id) {
      return {state:'retrust_required', error:'IDENTITY_CHANGED'};
    }
    return {state:'ready', error:null};
  }

  function resolveTrustedUrl(trustedDevice, peers) {
    const peer=(peers||[]).find(item=>item?.id&&item.id===trustedDevice?.id);
    if(!peer||!peer.ip)return trustedDevice?.url||'';
    try {
      const url=new URL(trustedDevice.url);
      url.hostname=peer.ip;
      url.port=String(peer.port||53317);
      return url.toString();
    } catch {
      return trustedDevice?.url||'';
    }
  }

  return {states, classify, resolveTrustedUrl};
});
