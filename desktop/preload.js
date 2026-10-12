'use strict'

/** What the studio page may use of the app: its backend's live feed. */
const { contextBridge, ipcRenderer } = require('electron')

function listen(channel, callback) {
  const handler = (_event, value) => callback(value)
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.removeListener(channel, handler)
}

contextBridge.exposeInMainWorld('agentforgeDesktop', {
  send: message => ipcRenderer.send('feed:send', message),
  onEvent: callback => listen('feed:event', callback),
  onStatus: callback => listen('feed:status', callback),
  version: () => ipcRenderer.sendSync('app:version'),
})
