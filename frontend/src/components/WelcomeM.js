import React, { useState, useEffect } from 'react';
import './component.css';
import CustomButton from './WelcomeButton'; 
import logo from '../assets/White-Logo.png';

const WelcomeModal = ({ onClose }) => {
  const [fadeOut, setFadeOut] = useState(false);

  // Check if the modal has already been shown in this session
  const [hasShownModal, setHasShownModal] = useState(false);

  useEffect(() => {
    const isModalShown = sessionStorage.getItem('hasShownModal');
    if (!isModalShown) {
      sessionStorage.setItem('hasShownModal', 'true');
      setHasShownModal(true); // Show the modal if not shown before
    }
  }, []);

  const handleClose = () => {
    setFadeOut(true);
    setTimeout(() => {
      onClose();
    }, 500);
  };

  // Only render the modal if it hasn't been shown before
  if (!hasShownModal) {
    return null; // Don't render anything if the modal should not be shown
  }

  return (
    <div className={`modal-overlay ${fadeOut ? 'fade-out' : ''}`}>
      <div className="modal">
        <img 
          src={logo} 
          alt="Lofu Logo" 
          style={{ 
            display: 'block', 
            margin: '0 auto', 
            width: '100px', 
            height: 'auto' 
          }} 
        />
        <h2 style={{ textAlign: 'center' }}>Welcome to Lofu!</h2>
        <p>Plantar pressure distribution refers to how weight and force are spread 
            across the bottom of your foot while standing, walking, or running. 
            By analyzing this pressure pattern, we can gain valuable insights into 
            foot health, posture, and gait. Additionally, it helps in diagnosing foot 
            deformities or conditions like flat feet, high arches, or bunions, as these
            can significantly alter pressure maps. For diabetics, monitoring pressure 
            distribution is essential for identifying high-pressure zones that could 
            lead to foot ulcers and other complications. It also plays a critical role 
            in evaluating the effectiveness of orthotics, as comparing pressure data 
            before and after using custom insoles can help determine if they provide 
            proper support. </p>

        <div className="button-container-right">
          <CustomButton label="Enter" onClick={handleClose} />
        </div>
      </div>
    </div>
  );
};

export default WelcomeModal;
