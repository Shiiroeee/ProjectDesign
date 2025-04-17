import React, { useState } from 'react';
import './component.css';
import CustomButton from './WelcomeButton'; // 
import logo from '../assets/White-Logo.png';

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
            By analyzing this pressure pattern,we can gain valuable insights into 
            foot health, posture, and gait. Additionally, it helps in diagnosing foot 
            deformities or conditions like flat feet, high arches, or bunions, as these
             can significantly alter pressure maps. For diabetics, monitoring pressure 
             distribution is essential for identifying high-pressure zones that could 
             lead to foot ulcers and other complications. It also plays a critical role 
             in evaluating the effectiveness of orthotics, as comparing pressure data 
             before and after using custom insoles can help determine if they provide 
             proper support. </p>

        {/* Replace default button with custom one */}
        <CustomButton label="Enter" onClick={handleClose} />
      </div>
    </div>
  );
};

export default WelcomeModal;
