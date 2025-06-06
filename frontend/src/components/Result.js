import React from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import icon from '../assets/White-Logo.png';
import '../App.css';
import './Screen.css';
import MainButton from './MainButton';

function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { images = [], results = [] } = location.state || {};

  const handleBack = () => navigate('/');

  const formatArchLabel = (label) => {
    switch (label) {
      case 'Flat':
        return 'Flat Arch';
      case 'Normal':
        return 'Normal Arch';
      case 'High':
        return 'High Arch';
      default:
        return label;
    }
  };

  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-logo">
          <img src={icon} alt="Logo" />
          <span>Lofu</span>
        </div>

        {/* Move the classification result header here */}
        <div className="navbar-title">
          <h3>Classification Results</h3>
        </div>

        <ul className="navbar-links">
          <li><Link to="/">Home</Link></li>
          <li><Link to="/result">Result</Link></li>
          <li><Link to="/recommended">Recommended</Link></li>
          <li><Link to="/information">Information</Link></li>
        </ul>
      </nav>

      <div className="result-body">
        {images.map((img, index) => (
          <div className="result-card" key={index}>
            <img src={img} alt={`Result ${index}`} className="result-image" />
            <div className="prediction-details">
              <h3>
                Prediction: <span>{formatArchLabel(results[index])}</span>
              </h3>
            </div>
          </div>
        ))}

        <div className="result-actions">
          <MainButton onClick={handleBack}>Back to Home</MainButton>
        </div>
      </div>
    </div>
  );
}

export default ResultPage;
