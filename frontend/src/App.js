// src/App.js
import React, { useState, useEffect, useRef } from 'react';
import icon from './assets/White-Logo.png';
import './App.css';
import WelcomeModal from './components/WelcomeM';
import MainButton from './components/MainButton';

function App() {
  const [showModal, setShowModal] = useState(true);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const overlayRef = useRef(null);
  const [capturedImages, setCapturedImages] = useState([]);
  const [detections, setDetections] = useState([]);

  // Start/stop camera
  useEffect(() => {
    let stream;

    const startCamera = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error('Error accessing camera', err);
      }
    };

    const stopCamera = () => {
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    };

    if (isCameraActive) {
      startCamera();
    } else {
      stopCamera();
    }

    return () => {
      stopCamera();
    };
  }, [isCameraActive]);

  // Handle capture
  const handleCapture = () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (video && canvas && video.videoWidth && video.videoHeight) {
      const ctx = canvas.getContext('2d');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = canvas.toDataURL('image/png');
      setCapturedImages((prev) => [...prev, imageData].slice(-3));
    }
  };

  // Handle detect
  const handleDetect = async () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (video && canvas && video.videoWidth && video.videoHeight) {
      const ctx = canvas.getContext('2d');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = canvas.toDataURL('image/png');

      try {
        const res = await fetch('http://127.0.0.1:5000/detect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: imageData }),
        });
        if (!res.ok) throw new Error('Server error');
        const boxes = await res.json();
        setDetections(boxes);
      } catch (err) {
        console.error('Detection error', err);
      }
    }
  };

  // Draw detections
  useEffect(() => {
    const canvas = overlayRef.current;
    const ctx = canvas?.getContext('2d');
    const video = videoRef.current;

    if (canvas && ctx && video && video.videoWidth && video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = 'lime';
      ctx.lineWidth = 2;
      ctx.font = '16px sans-serif';
      ctx.fillStyle = 'lime';

      detections.forEach((d) => {
        const { x1, y1, x2, y2, class: cls, confidence } = d;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.fillText(`${cls} ${(confidence * 100).toFixed(1)}%`, x1, y1 - 4);
      });
    }
  }, [detections]);

  const handleDelete = (i) => {
    setCapturedImages((prev) => prev.filter((_, idx) => idx !== i));
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
          {[0, 1].map((i) => (
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
              <div className="video-wrapper">
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  className="camera-feed"
                  onLoadedMetadata={() => {
                    const canvas = overlayRef.current;
                    const video = videoRef.current;
                    if (canvas && video) {
                      canvas.width = video.videoWidth;
                      canvas.height = video.videoHeight;
                    }
                  }}
                />
                <canvas ref={overlayRef} className="overlay-canvas" />
              </div>
            ) : (
              <p>Camera is off</p>
            )}

            <canvas ref={captureCanvasRef} style={{ display: 'none' }} />

            <div className="camera-buttons">
              <MainButton onClick={handleCapture}>Capture</MainButton>
              <MainButton onClick={handleDetect}>Detect</MainButton>
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
