const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { trustedMedia, exportOptions, installCapabilities } = require('../capabilities.cjs');
const origin = 'http://127.0.0.1:18080';
function fixture() {
  const contents = new EventEmitter();
  contents.mainFrame = { url: origin + '/settings' };
  contents.getURL = () => contents.mainFrame.url;
  const window = { isDestroyed: () => false, webContents: contents };
  const details = { isMainFrame: true, requestingUrl: contents.getURL(), mediaTypes: ['audio'] };
  return { contents, window, details };
}

test('microphone allows only owned top-frame audio requests', () => {
  const { contents, window, details } = fixture();
  assert.ok(trustedMedia(contents, 'media', details, window, origin));
  for (const change of [{ isMainFrame: false }, { mediaTypes: ['video'] }, { mediaTypes: ['audio', 'video'] },
    { mediaTypes: [] }, { mediaTypes: undefined }, { requestingUrl: origin + '1' }, { securityOrigin: 'https://example.com' }]) {
    assert.equal(trustedMedia(contents, 'media', { ...details, ...change }, window, origin), false);
  }
  assert.equal(trustedMedia({}, 'media', details, window, origin), false);
  assert.equal(trustedMedia(contents, 'display-capture', details, window, origin), false);
  assert.equal(trustedMedia(contents, 'media', { ...details, mediaType: 'unknown' }, window, origin, true), false);
});

test('exports reject foreign initiators, subframes, redirects, unsafe names and executable types', () => {
  const { contents, window } = fixture();
  const item = { getInitiatorOrigin: () => origin, getURLChain: () => ['blob:' + origin + '/example'], getFilename: () => '学习报告.pdf' };
  const options = exportOptions(item, contents, contents.mainFrame, window, origin);
  assert.equal(options.defaultPath, '学习报告.pdf');
  assert.deepEqual(options.properties, ['showOverwriteConfirmation']);
  assert.equal(exportOptions(item, contents, { ...contents.mainFrame }, window, origin), null);
  assert.equal(exportOptions(item, contents, null, window, origin), null);
  assert.equal(exportOptions({ ...item, getInitiatorOrigin: () => '' }, contents, contents.mainFrame, window, origin), null);
  for (const filename of ['../x.pdf', 'C:\\x.pdf', 'x.exe', 'CON.pdf', 'x.pdf ', 'x.pdf:evil', 'x' + String.fromCodePoint(0x202e) + '.pdf']) {
    assert.equal(exportOptions({ ...item, getFilename: () => filename }, contents, contents.mainFrame, window, origin), null);
  }
  for (const urls of [[], ['data:text/plain,hello'], ['blob:https://example.com/1'], [origin + '/arbitrary.pdf'],
    [origin + '/api/v1/exports/1/download', 'https://example.com/payload']]) {
    assert.equal(exportOptions({ ...item, getURLChain: () => urls }, contents, contents.mainFrame, window, origin), null);
  }
  for (const ext of ['json', 'md', 'pdf', 'docx', 'pptx']) {
    assert.ok(exportOptions({ ...item, getFilename: () => '学习.' + ext }, contents, contents.mainFrame, window, origin));
  }
  assert.ok(exportOptions({ ...item, getURLChain: () => [origin + '/api/v1/exports/1/download'] }, contents, contents.mainFrame, window, origin));
});

test('microphone denial, consent, reload and pending-navigation race fail closed', async () => {
  const { contents, window, details } = fixture();
  const profile = new EventEmitter();
  let request, check, answer = 0, resolveDialog;
  profile.setPermissionRequestHandler = value => { request = value; };
  profile.setPermissionCheckHandler = value => { check = value; };
  const dialog = { showMessageBox: async () => answer === 'pending' ? new Promise(resolve => { resolveDialog = resolve; }) : { response: answer } };
  installCapabilities(profile, window, origin, dialog);
  const ask = () => new Promise(resolve => request(contents, 'media', resolve, details));
  const granted = () => check(contents, 'media', origin, { ...details, mediaType: 'audio' });
  assert.equal(granted(), false);
  assert.equal(await ask(), false);
  answer = 1;
  assert.equal(await ask(), true);
  assert.equal(granted(), true);
  assert.equal(check(contents, 'media', origin, { ...details, mediaType: 'video' }), false);
  contents.emit('did-start-navigation', {}, origin, false, true);
  assert.equal(granted(), false);
  answer = 'pending';
  const pending = ask();
  assert.equal(await ask(), false);
  contents.emit('did-start-navigation', {}, origin, false, true);
  resolveDialog({ response: 1 });
  assert.equal(await pending, false);
  assert.equal(granted(), false);
});
