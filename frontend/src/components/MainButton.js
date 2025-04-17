import React from 'react';
import './component.css'; // Add styles here

const MainButton = ({ onClick, children }) => {
  return (
    <button className="gradient-btn" onClick={onClick}>
      {children}
    </button>
  );
};

export default MainButton;