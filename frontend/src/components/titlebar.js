import React from 'react';
import './component.css';

const CustomTitleBar = () => {
  const { ipcRenderer } = window.require('electron');

  return (
    <div className="custom-title-bar">
      <div className="title">My App</div>
      <div className="window-controls">
        <button onClick={() => ipcRenderer.send('minimize')}>–</button>
        <button onClick={() => ipcRenderer.send('maximize')}>□</button>
        <button onClick={() => ipcRenderer.send('close')}>×</button>
      </div>
    </div>
  );
};

export default CustomTitleBar;
