import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import icon from './assets/White-Logo.png';
import './App.css';
import WelcomeModal from './components/WelcomeM';
import MainButton from './components/MainButton';

function App() {
  const [showModal, setShowModal] = useState(true);
  const [capturedImage, setCapturedImage] = useState(null);
  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);

  useEffect(() => {
    let stream;
    navigator.mediaDevices.getUserMedia({ video: true })
      .then((s) => {
        stream = s;
        videoRef.current.srcObject = stream;
      })
      .catch((err) => console.error('Camera error:', err));

    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const handleCapture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return;

    const canvas = captureCanvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const dataURL = canvas.toDataURL('image/png');
    setCapturedImage(dataURL);
  };

  const handleDetect = async () => {
    if (!capturedImage) {
      alert('Please capture an image first.');
      return;
    }

    try {
      const response = await fetch('http://localhost:5000/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: capturedImage })
      });

      const detections = await response.json();

      if (!Array.isArray(detections)) {
        alert('Detection failed or returned no valid response.');
        return;
      }

      drawBoundingBoxes(detections);
    } catch (error) {
      console.error('Detection error:', error);
      alert('Detection failed.');
    }
  };

  const drawBoundingBoxes = (boxes) => {
    const canvas = captureCanvasRef.current;
    const ctx = canvas.getContext('2d');

    const image = new Image();
    image.onload = () => {
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.font = '16px Arial';
      ctx.fillStyle = 'red';

      boxes.forEach(box => {
        const { x1, y1, x2, y2, class: className } = box;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.fillText(className, x1, y1 - 5);
      });

      const updatedImage = canvas.toDataURL('image/png');
      setCapturedImage(updatedImage);
    };
    image.src = capturedImage;
  };

  return (
    <div className="App">
      <nav className="navbar">
        <div className="navbar-logo">
          <img src={icon} alt="Logo" />
          <span>Lofu</span>
        </div>
        <ul className="navbar-links">
          <li><Link to="/">Home</Link></li>
          <li><Link to="/result">Result</Link></li>
          <li><Link to="/recommended">Recommended</Link></li>
          <li><Link to="/information">Information</Link></li>
        </ul>
      </nav>

      {showModal && <WelcomeModal onClose={() => setShowModal(false)} />}

      <div className="main-body-vertical">
        {/* Left: Canvas with Bounding Boxes */}
        <div className="left-section">
          {capturedImage ? (
            <canvas ref={captureCanvasRef} className="full-capture-img" />
          ) : (
            <span className="placeholder">No image captured</span>
          )}
          <div style={{ marginTop: '20px' }}>
            <MainButton onClick={handleDetect}>Detect</MainButton>
          </div>
        </div>

        {/* Right: Live Camera */}
        <div className="right-section">
          <div className="camera-container">
            <video ref={videoRef} autoPlay muted className="camera-feed" />
            <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
            <div className="camera-buttons">
              <MainButton onClick={handleCapture}>Capture</MainButton>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
