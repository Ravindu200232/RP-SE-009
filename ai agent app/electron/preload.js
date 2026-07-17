const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("locode", {
    // Existing channels
    onStatus: (cb) => ipcRenderer.on("status", (_e, msg) => cb(msg)),
    onLog: (cb) => ipcRenderer.on("log", (_e, line) => cb(line)),

    // First-time setup channel
    onSetup: (cb) => ipcRenderer.on("setup", (_e, msg) => cb(msg)),

    // Project folder upload (returns { name, path, files, fileCount } or null)
    chooseFolder: () => ipcRenderer.invoke("choose-folder"),

    // Open a URL in the system browser
    openExternal: (url) => ipcRenderer.invoke("open-external", url),
});