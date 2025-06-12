import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../style/Popup.css';

export default function GlobalPopup() {
  const [visible, setVisible] = useState(false);
  const [message, setMessage] = useState('');
  const [currentKey, setCurrentKey] = useState('');

  useEffect(() => {
    const checkNewImage = async () => {
      try {
        const { data } = await axios.get('http://127.0.0.1:5500/api/latest-image-key');
        const latestKey = data.key;

        const lastDismissedKey = localStorage.getItem('last_seen_image_key');

        if (latestKey && latestKey !== lastDismissedKey) {
          const res = await axios.post('http://127.0.0.1:5500/api/process-latest');

          if (res.data.status === 'success') {
            const plant = res.data.entry?.disease_class?.name?.split("___")[0] || 'Unknown';
            setMessage(plant);
            setCurrentKey(latestKey);
            setVisible(true);
          }
        }
      } catch (err) {
        console.error('Popup image check error:', err);
      }
    };

    checkNewImage();
    const id = setInterval(checkNewImage, 10000);
    return () => clearInterval(id);
  }, []);

  const handleClose = () => {
    localStorage.setItem('last_seen_image_key', currentKey);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="popup-overlay">
      <div className="popup-box">
        <p>{message}</p>
        <button className="btn btn-success" onClick={handleClose}>Close</button>
      </div>
    </div>
  );
}