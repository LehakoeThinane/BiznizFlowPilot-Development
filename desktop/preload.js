// Runs in the renderer with Node access, before the page loads, but the
// renderer itself stays fully sandboxed (contextIsolation: true in main.js).
// Nothing is exposed yet - this is the seam for future desktop-only
// integrations (native notifications, unread badge count, etc.) without
// ever having to turn nodeIntegration on for a window loading remote content.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("bfpDesktop", {
  isDesktopApp: true,
});
