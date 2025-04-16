import React, { useState } from 'react';
import icon from './assets/White-Logo.png';  
import './App.css';
import WelcomeModal from './components/WelcomeM';

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
          <li><a href="#">Home</a></li>
          <li><a href="#">Features</a></li>
          <li><a href="#">About</a></li>
        </ul>
      </nav>

      {showModal && <WelcomeModal onClose={() => setShowModal(false)} />}

      <div className="app-container">
        <h1>Welcome to My React App</h1>
      </div>
    </div>
  );
}

export default App;
