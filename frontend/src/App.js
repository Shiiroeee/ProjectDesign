import React, { useState } from 'react';
import icon from './assets/White-Logo.png';  
import './App.css';
import WelcomeModal from './components/WelcomeM';
import MainButton from './components/MainButton';

function App() {
  const [showModal, setShowModal] = useState(true);

  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-logo">
          <img src={icon} alt="Logo" />
          <span>Lofu</span>
        </div>
        <ul className="navbar-links">
          <li><a href="">Result</a></li>
          <li><a href="#">Recommended</a></li>
          <li><a href="#">Information</a></li>
        </ul>
      </nav>

      {showModal && <WelcomeModal onClose={() => setShowModal(false)} />}

      <div className="main-body-vertical">
        <div className="left-section">
          {/* Place content like camera here */}
          <h2>Left Side</h2>
        </div>
        <div className="right-section">
          {/* Place content like button or results here */}
          <MainButton onClick={() => console.log('Main button clicked!')}>
            Capture
          </MainButton>
        </div>
      </div>
    </div>
  );
}

export default App;
