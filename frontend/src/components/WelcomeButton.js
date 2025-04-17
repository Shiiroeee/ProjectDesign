import React, { useState } from 'react';
import './component.css';

const CustomButton = ({ label, onClick }) => {
  const [clicked, setClicked] = useState(false);

  const handleClick = () => {
    setClicked(true);
    onClick();
    setTimeout(() => setClicked(false), 300); // reset after animation
  };

  return (
    <button
      className={`custom-btn ${clicked ? 'clicked' : ''}`}
      onClick={handleClick}
    >
      {label}
    </button>
  );
};

export default CustomButton;
