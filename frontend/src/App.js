import React, { useState, useEffect, useRef } from 'react';
import icon from './assets/White-Logo.png';  
import './App.css';
import WelcomeModal from './components/WelcomeM';
import MainButton from './components/MainButton';

function App() {
  const [showModal, setShowModal] = useState(true);
  const [isCameraActive, setIsCameraActive] = useState(false); // State to toggle camera on/off
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [capturedImages, setCapturedImages] = useState([]);

  useEffect(() => {
    let stream;

    const startCamera = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (error) {
        console.error('Error accessing the camera', error);
      }
    };

    const stopCamera = () => {
      const tracks = videoRef.current?.srcObject?.getTracks();
      tracks?.forEach(track => track.stop());
    };

    if (isCameraActive) {
      startCamera();
    } else {
      stopCamera();
    }

    // Cleanup on component unmount
    return () => stopCamera();
  }, [isCameraActive]);

  const handleCapture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (video && canvas) {
      const context = canvas.getContext('2d');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = canvas.toDataURL('image/png');
      setCapturedImages(prev => {
        const newImages = [...prev, imageData];
        return newImages.slice(-3); // Only keep last 3 images
      });
    }
  };

  const handleDelete = (indexToDelete) => {
    setCapturedImages(prev => prev.filter((_, index) => index !== indexToDelete));
  };

  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-logo">
          <img src={icon} alt="Logo" />
          <span>Lofu</span>
        </div>
        <ul className="navbar-links">
          <li><a href="#">Home</a></li>
          <li><a href="#">Result</a></li>
          <li><a href="#">Recommended</a></li>
          <li><a href="#">Information</a></li>
        </ul>
      </nav>

      {showModal && <WelcomeModal onClose={() => setShowModal(false)} />}

      <div className="main-body-vertical">
        <div className="left-section">
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="image-slot" key={i}>
              {capturedImages[i] ? (
                <>
                  <img src={capturedImages[i]} alt={`Capture ${i + 1}`} />
                  <button className="delete-btn" onClick={() => handleDelete(i)}>✖</button>
                </>
              ) : (
                <span className="placeholder">Empty Slot</span>
              )}
            </div>
          ))}
        </div>

        <div className="right-section">
          <div className="camera-container">
            {isCameraActive ? (
              <>
                <video ref={videoRef} autoPlay muted className="camera-feed" />
                <canvas ref={canvasRef} style={{ display: 'none' }} />
              </>
            ) : (
              <p>Camera is off</p>
            )}
            <div className="camera-buttons">
              <MainButton onClick={handleCapture}>
                Capture
              </MainButton>
              <button 
                onClick={() => setIsCameraActive(!isCameraActive)} 
                className="gradient-btn"
              >
                {isCameraActive ? 'Stop Camera' : 'Start Camera'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
