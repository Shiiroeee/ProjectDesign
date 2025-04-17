import React, { useState, useEffect, useRef } from 'react';
import icon from './assets/White-Logo.png';  
import './App.css';
import WelcomeModal from './components/WelcomeM';

function App() {
  const [showModal, setShowModal] = useState(true);
  const videoRef = useRef(null); // To reference the video element

  useEffect(() => {
    // Request camera access
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error("Error accessing the camera", err);
      }
    };

    startCamera();

    // Cleanup: stop all video tracks when the component unmounts
    return () => {
      const stream = videoRef.current?.srcObject;
      const tracks = stream?.getTracks();
      tracks?.forEach((track) => track.stop());
    };
  }, []);

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

    </div>
  );
}

export default App;
