// src/CapturedImagesContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';

const CapturedImagesContext = createContext();

export const useCapturedImages = () => {
  return useContext(CapturedImagesContext);
};

export const CapturedImagesProvider = ({ children }) => {
  const [capturedImages, setCapturedImages] = useState(() => {
    const stored = localStorage.getItem('capturedImages');
    return stored ? JSON.parse(stored) : [];
  });

  useEffect(() => {
    localStorage.setItem('capturedImages', JSON.stringify(capturedImages));
  }, [capturedImages]);

  const addCapturedImage = (imageData) => {
    setCapturedImages((prev) => [...prev, imageData]);
  };

  const removeCapturedImage = (index) => {
    setCapturedImages((prev) => prev.filter((_, idx) => idx !== index));
  };

  return (
    <CapturedImagesContext.Provider
      value={{
        capturedImages,
        addCapturedImage,
        removeCapturedImage,
      }}
    >
      {children}
    </CapturedImagesContext.Provider>
  );
};
