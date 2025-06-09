import React, { useEffect, useState } from 'react';
import axios from 'axios';
import '../style/Dashboard.css';
import '../style/History.css';
import PageWrapper from '../component/PageWrapper';

export default function History() {
  const [timestamps, setTimestamps] = useState([]);
  const [selectedTimestamp, setSelectedTimestamp] = useState(null);
  const [selectedData, setSelectedData] = useState(null);

  // Fetch and sort all available timestamps on component mount
  useEffect(() => {
    axios.get('http://localhost:5500/api/sensor-data')
      .then(res => {
        const data = res.data;
        const validTimestamps = data
          .filter(entry => entry.timestamp)
          .map(entry => entry.timestamp)
          .sort((a, b) => new Date(b) - new Date(a)); // descending order
        setTimestamps(validTimestamps);
      })
      .catch(err => console.error('Error loading timestamps:', err));
  }, []);

  // Handle selection and toggle of a timestamp
  const handleClick = (timestamp) => {
    if (selectedTimestamp === timestamp) {
      setSelectedTimestamp(null);
      setSelectedData(null);
    } else {
      setSelectedTimestamp(timestamp);
      axios.get('http://localhost:5500/api/sensor-data')
        .then(res => {
          const data = res.data;
          const match = data.find(entry => entry.timestamp === timestamp);
          setSelectedData(match || null);
        })
        .catch(err => console.error('Error loading sensor data:', err));
    }
  };

  // Format timestamp for UI display
  const formatTimestamp = (ts) => {
    const [date, time] = ts.split('T');
    return `${date} at ${time}`;
  };

  return (
    <PageWrapper>
      <div>
        <h1 className="mb-4">Sensor Data History</h1>

        <section className="timestamps-list">
          <h2>Select a Date</h2>
          <ul className="list-unstyled">
            {timestamps.map(ts => (
              <li key={ts} className="mb-2">
                <button
                  onClick={() => handleClick(ts)}
                  className={`timestamp-btn ${selectedTimestamp === ts ? 'active' : ''}`}
                >
                  {formatTimestamp(ts)}
                </button>

                {selectedTimestamp === ts && selectedData && (
                  <div className="sensor-card p-3 mt-2 border rounded bg-light">
                    <p><strong>Temperature:</strong> {selectedData.air_temperature_C} °C</p>
                    <p><strong>Humidity:</strong> {selectedData.air_humidity} %</p>
                    <p><strong>UV Light:</strong> {selectedData.light_intensity} mW/cm²</p>
                    <p><strong>Soil Moisture:</strong> {selectedData.soil_humidity} %</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </PageWrapper>
  );
}