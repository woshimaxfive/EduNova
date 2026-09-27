const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('codeJob', {
  receive: callback => ipcRenderer.once('edunova:verify-job', (_event, payload) => callback(payload)),
  ready: () => ipcRenderer.send('edunova:verify-ready'),
  result: value => ipcRenderer.send('edunova:verify-result', value),
});
