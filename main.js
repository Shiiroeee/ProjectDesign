const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let pyProc;
function startBackend() {
  const script = path.join(__dirname, 'backend', 'app.py');
  const python = process.platform==='win32'
    ? path.join(__dirname,'backend','venv','Scripts','python.exe')
    : 'python3';
  pyProc = spawn(python, [script], { cwd: path.join(__dirname,'backend') });
  pyProc.stdout.on('data', d => console.log(`PY: ${d}`));
}
function stopBackend() {
  if (pyProc) pyProc.kill();
}

app.whenReady().then(() => {
  startBackend();
  createWindow();
});
app.on('before-quit', stopBackend);
