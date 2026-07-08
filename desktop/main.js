// BiznizFlowPilot desktop shell - a thin wrapper around the hosted web app,
// the same pattern Slack/Teams/Discord/Notion use for their desktop clients.
// All product logic (frontend + backend) lives on the server; this process
// only owns the native window and a few desktop-appropriate behaviors
// (external links open in the OS browser, not inside the app).

const { app, BrowserWindow, shell } = require("electron");
const { autoUpdater } = require("electron-updater");
const path = require("path");

// Only the app shell (this file, icon, native menu, Electron/Chromium
// version) ever needs an update via this mechanism - the actual product
// (frontend + backend) is loaded fresh from APP_URL on every launch, same
// as a website, so most releases need no desktop update at all.
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;

// Overridable for local development against a dev server; defaults to the
// hosted production app.
const APP_URL = process.env.BFP_APP_URL || "https://app.mmnexus.co.za";

let mainWindow = null;

function isSameOrigin(targetUrl) {
  try {
    return new URL(targetUrl).origin === new URL(APP_URL).origin;
  } catch {
    return false;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    title: "BiznizFlowPilot",
    backgroundColor: "#0a0a0a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadURL(APP_URL);

  // Keep in-app navigation scoped to our own origin. Anything else (a
  // support link, a third-party OAuth redirect, etc.) opens in the user's
  // default browser instead of navigating the app window away from itself.
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isSameOrigin(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isSameOrigin(url)) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  // Silent check - downloads in the background if a newer shell version is
  // published, applies automatically the next time the user quits the app
  // (autoInstallOnAppQuit above), so there's no disruptive "restart now?"
  // prompt during a work session.
  autoUpdater.checkForUpdatesAndNotify().catch(() => {
    // No published feed configured yet, offline, or dev/unpackaged run -
    // never let a failed update check block the app from opening.
  });

  app.on("activate", () => {
    // macOS convention: clicking the dock icon re-opens a window if none exist.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  // Windows/Linux convention: quit when the last window closes.
  // macOS convention: stay running until the user explicitly quits.
  if (process.platform !== "darwin") app.quit();
});
