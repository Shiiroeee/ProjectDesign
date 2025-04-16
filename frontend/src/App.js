// frontend/src/App.js
import React, { useState } from 'react';
import './App.css';

function App() {
  const [input, setInput] = useState('');
  const [result, setResult] = useState('');

  const handlePredict = async () => {
    const res = await fetch('http://localhost:5000/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input }),
    });
    const data = await res.json();
    setResult(data.result);
  };

  return (
    <div className="App">
      <h1>🧦 CozyFeet Predictor</h1>
      <input
        placeholder="Type something cozy..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      <button onClick={handlePredict}>Predict</button>
      <p>{result}</p>
    </div>
  );
}

export default App;
