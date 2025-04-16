import React, {useState } from 'react';
import './component.css';

const WelcomeModal = ({ onClose }) => {
  const [fadeOut, setFadeOut] = useState(false);

  const handleClose = () => {
    setFadeOut(true);
    setTimeout(() => {
      onClose();
    }, 500); 
  };

  return (
    <div className={`modal-overlay ${fadeOut ? 'fade-out' : ''}`}>
      <div className="modal">
        <h2>Welcome to Lofu</h2>
        <p>Your cozy companion for foot health and warmth monitoring.</p>
        <button className="modal-btn" onClick={handleClose}>Enter</button>
      </div>
    </div>
  );
};

export default WelcomeModal;
