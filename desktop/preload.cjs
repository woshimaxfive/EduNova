const { contextBridge, ipcRenderer } = require('electron');
// No generic send/invoke, filesystem, URL, command or manifest access.
contextBridge.exposeInMainWorld('eduNovaDesktop', Object.freeze({
  status: () => ipcRenderer.invoke('edunova:status'),
  quit: () => ipcRenderer.invoke('edunova:quit')
}));
