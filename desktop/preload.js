const { contextBridge, ipcRenderer } = require('electron')

// Simple secure bridge to expose native OS properties required by UI (if any).
// Web app mostly talks via HTTP to the Python backend on localhost port 5055.
contextBridge.exposeInMainWorld('electronAPI', {
    getPlatform: () => ipcRenderer.invoke('get-platform'),
    isDesktop: true
})
