const { test } = require('node:test');
const assert = require('node:assert/strict');
const { trustedSender } = require('../config.cjs');
test('IPC accepts only the owned top frame and exact origin', () => {
  const frame = {url:'http://127.0.0.1:18080/app'};
  const contents = {mainFrame:frame};
  const window = {isDestroyed:()=>false,webContents:contents};
  assert.equal(trustedSender({sender:contents,senderFrame:frame},window,'http://127.0.0.1:18080'),true);
  assert.equal(trustedSender({sender:{},senderFrame:frame},window,'http://127.0.0.1:18080'),false);
  assert.equal(trustedSender({sender:contents,senderFrame:{...frame}},window,'http://127.0.0.1:18080'),false);
  frame.url='http://127.0.0.1:18081/app';
  assert.equal(trustedSender({sender:contents,senderFrame:frame},window,'http://127.0.0.1:18080'),false);
  frame.url='https://example.com';
  assert.equal(trustedSender({sender:contents,senderFrame:frame},window,'http://127.0.0.1:18080'),false);
  assert.equal(trustedSender({sender:contents,senderFrame:null},window,'http://127.0.0.1:18080'),false);
});
