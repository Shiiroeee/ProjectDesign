import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import icon from './assets/White-Logo.png';
import './App.css';
import WelcomeModal from './components/WelcomeM';
import MainButton from './components/MainButton';

function App() {
  const [showModal, setShowModal] = useState(true);
  const [capturedImage, setCapturedImage] = useState(null); // current image shown in right panel
  const [savedImages, setSavedImages] = useState([]);       // images saved on left panel
  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const streamRef = useRef(null);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error('Camera error:', err);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  // Capture current frame from video into canvas (original size)
  const handleCapture = () => {
    const video = videoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas || !video.videoWidth || !video.videoHeight) return;

    // Draw original video frame on canvas
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Get dataURL (original size)
    const dataURL = canvas.toDataURL('image/png');
    setCapturedImage(dataURL);
  };

  // Detect function: resize image to 640x480, send to server, get bounding boxes and draw them
  const handleDetect = async () => {
    if (!capturedImage) {
      alert('Please capture an image first.');
      return;
    }

    // Resize image to 640x480 on temp canvas before sending
    const img = new Image();
    img.src = capturedImage;
    img.onload = async () => {
      const resizeCanvas = document.createElement('canvas');
      resizeCanvas.width = 640;
      resizeCanvas.height = 480;
      const ctx = resizeCanvas.getContext('2d');
      ctx.drawImage(img, 0, 0, 640, 480);

      const resizedDataURL = resizeCanvas.toDataURL('image/png');

      try {
        const response = await fetch('http://localhost:5000/detect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ image: resizedDataURL }),
        });

        const detections = await response.json();

        if (!Array.isArray(detections)) {
          alert('Detection failed or returned no valid response.');
          return;
        }

        drawBoundingBoxes(detections, resizedDataURL);
      } catch (error) {
        console.error('Detection error:', error);
        alert('Detection failed.');
      }
    };
  };

  // Draw bounding boxes on canvas of size 640x480 and update capturedImage state
  const drawBoundingBoxes = (boxes, imageSrc) => {
    const canvas = captureCanvasRef.current;
    const ctx = canvas.getContext('2d');

    const image = new Image();
    image.onload = () => {
      canvas.width = 640;
      canvas.height = 480;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, 640, 480);

      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.font = '16px Arial';
      ctx.fillStyle = 'red';

      boxes.forEach((box) => {
        const { x1, y1, x2, y2, class: className } = box;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.fillText(className, x1, y1 - 5);
      });

      const updatedImage = canvas.toDataURL('image/png');

      setCapturedImage(updatedImage);
    };
    image.src = imageSrc;
  };

  // When user clicks capture, save current capturedImage (with bounding boxes) to left panel
  const handleSaveCapture = () => {
    if (!capturedImage) {
      alert('No image to save. Please capture and detect first.');
      return;
    }
    setSavedImages((prev) => {
      const newImages = [capturedImage, ...prev];
      return newImages.slice(0, 2); // keep max 2 images
    });
  };

  const handleClassify = () => {
    alert('Classify clicked (you can connect this to your model)');
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
        {/* LEFT SIDE */}
        <div className="left-section">
          <div className="image-pair-row">
            <div className="image-box">
              {savedImages[0] ? (
                <img src={savedImages[0]} alt="Saved 1" />
              ) : (
                <div className="placeholder">No image yet</div>
              )}
            </div>
            <div className="image-box">
              {savedImages[1] ? (
                <img src={savedImages[1]} alt="Saved 2" />
              ) : (
                <div className="placeholder">No image yet</div>
              )}
            </div>
          </div>
          <div style={{ marginTop: '20px' }}>
            <MainButton onClick={handleClassify}>Classify</MainButton>
          </div>
        </div>

        {/* RIGHT SIDE */}
        <div className="right-section">
          {capturedImage ? (
            <div className="captured-wrapper">
              <div className="image-slot">
                <img src={capturedImage} alt="Captured" />
                <button className="exit-icon" onClick={() => setCapturedImage(null)}>×</button>
              </div>
              <div className="detect-capture-buttons">
                <MainButton onClick={handleDetect}>Detect</MainButton>
                <MainButton onClick={handleSaveCapture}>Capture</MainButton>
              </div>
            </div>
          ) : (
            <div className="camera-container">
              <video ref={videoRef} autoPlay muted className="camera-feed" />
              <div className="camera-buttons">
                <MainButton onClick={handleCapture}>Capture</MainButton>
              </div>
            </div>
          )}
          <canvas ref={captureCanvasRef} style={{ display: 'none' }} />
        </div>
      </div>
    </div>
  );
}

export default App;
