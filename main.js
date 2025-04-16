const { app, BrowserWindow } = require('electron');
const path = require('path');

let splash;
let mainWindow;

function createWindow() {
  // Splash window
  splash = new BrowserWindow({
    width: 400,
    height: 300,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
  });

  splash.loadFile('splash.html');

  // Main app window (React app)
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    show: false, // Important: keep hidden initially
    webPreferences: {
      contextIsolation: false,
      nodeIntegration: true,
    },
  });

  mainWindow.loadFile('frontend/build/index.html');

  // Show main window when ready
  mainWindow.once('ready-to-show', () => {
    setTimeout(() => {
      splash.close();
      mainWindow.show();
    }, 1500); // Optional delay
  });
}

app.whenReady().then(createWindow);
