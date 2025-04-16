import React, { useState, useEffect, useRef } from 'react';
import icon from './assets/White-Logo.png';  
import './App.css';
import WelcomeModal from './components/WelcomeM';

function App() {
  const [showModal, setShowModal] = useState(true);
  const videoRef = useRef(null); // To reference the video element
  const canvasRef = useRef(null); // To reference the canvas for capturing the image
  const [capturedImage, setCapturedImage] = useState(null); // To store captured image as base64

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

  // Function to capture the image from video
  const captureImage = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (video && canvas) {
      const context = canvas.getContext('2d');
      // Set the canvas size to the video frame size
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      // Draw the current video frame on the canvas
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      // Get the image data URL (base64 encoded)
      const imageUrl = canvas.toDataURL('image/png');
      setCapturedImage(imageUrl); // Store the captured image
    }
  };

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

      <div className="app-container">
        {/* Video element for camera feed */}
        <video 
          ref={videoRef} 
          autoPlay 
          muted 
          style={{ width: '100%', height: 'auto' }}
        ></video>

        {/* Button to capture image */}
        <button onClick={captureImage} className="capture-button">
          Capture
        </button>

        {/* Display the captured image */}
        {capturedImage && (
          <div className="captured-image-container">
            <h3>Captured Image:</h3>
            <img src={capturedImage} alt="Captured" style={{ width: '100%', height: 'auto' }} />
          </div>
        )}
        
        {/* Canvas for capturing the image */}
        <canvas ref={canvasRef} style={{ display: 'none' }}></canvas>
      </div>
    </div>
  );
}

export default App;
