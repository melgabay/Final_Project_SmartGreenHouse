import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import PageWrapper from '../component/PageWrapper';
import '../style/Settings.css';

export default function Settings() {
  const [sensorData, setSensorData] = useState({
    temperature: 0,
    humidity: 0,
    uv_light: 0,
    soil_moisture: 0,
  });

  const [wateringTime, setWateringTime] = useState('08:00');
  const [lightingTime, setLightingTime] = useState('10:00');
  const [plantProfile, setPlantProfile] = useState(() => localStorage.getItem('selectedPlant') || '');
  const [plantProfiles, setPlantProfiles] = useState([]);
  const [notifications, setNotifications] = useState(false);
  const [storage, setStorage] = useState(false);

  // Fetch latest sensor values
  useEffect(() => {
    const fetchLatestSensorData = async () => {
      try {
        const res = await axios.get('http://localhost:5500/api/latest-sensor');
        const data = res.data;
        setSensorData({
          temperature: data.air_temperature_C ?? 0,
          humidity: data.air_humidity ?? 0,
          uv_light: data.light_intensity ?? 0,
          soil_moisture: data.soil_humidity ?? 0,
        });
      } catch (error) {
        console.error('Error loading latest sensor data:', error);
      }
    };

    fetchLatestSensorData();
  }, []);

  // Fetch list of available plant profiles
  useEffect(() => {
    const fetchPlantProfiles = async () => {
      try {
        const res = await axios.get('http://localhost:5500/api/plant_data');
        const data = res.data;
        const profiles = Object.keys(data);
        setPlantProfiles(profiles);

        // If current profile isn't valid, select the first one
        if (!profiles.includes(plantProfile) && profiles.length > 0) {
          setPlantProfile(profiles[0]);
        }
      } catch (error) {
        console.error('Error loading plant profiles:', error);
      }
    };

    fetchPlantProfiles();
  }, [plantProfile]);

  // Save selected plant to local storage
  useEffect(() => {
    if (plantProfile) {
      localStorage.setItem('selectedPlant', plantProfile);
    }
  }, [plantProfile]);

  return (
    <PageWrapper>
      <main>
        <h1 className="mb-4">Settings</h1>
        <div className="settings-grid">

          {/* Sensor data display */}
          <section className="sect thresholds">
            <h2>Latest Measurements</h2>
            <div className="setting-item">Temperature: <span>{sensorData.temperature} °C</span></div>
            <div className="setting-item">Humidity: <span>{sensorData.humidity} %</span></div>
            <div className="setting-item">UV Light: <span>{sensorData.uv_light} mW/cm²</span></div>
            <div className="setting-item">Soil Moisture: <span>{sensorData.soil_moisture} %</span></div>
          </section>

          {/* Time schedule settings */}
          <section className="sect schedule">
            <h2>Schedule</h2>
            <div className="setting-item">
              Watering
              <input type="time" value={wateringTime} onChange={e => setWateringTime(e.target.value)} />
            </div>
            <div className="setting-item">
              Lighting
              <input type="time" value={lightingTime} onChange={e => setLightingTime(e.target.value)} />
            </div>
          </section>

          {/* Plant profile selector */}
          <section className="sect plant-profile">
            <h2>Plant Profile</h2>
            <select value={plantProfile} onChange={e => setPlantProfile(e.target.value)}>
              {plantProfiles.map(profile => (
                <option key={profile} value={profile}>{profile}</option>
              ))}
            </select>
            <div className="current-plant mt-2">
              <strong>Selected Plant:</strong> {plantProfile}
            </div>
          </section>

          {/* Account / Preferences */}
          <section className="sect account">
            <h2>Account</h2>
            <div className="setting-item switch-wrapper">
              <span>Notifications</span>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={notifications}
                  onChange={() => setNotifications(!notifications)}
                />
                <span className="slider" />
              </label>
            </div>

            <div className="setting-item">
              <Link to="/change-password">Change Password &gt;</Link>
            </div>

            <div className="setting-item switch-wrapper">
              <span>Storage</span>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={storage}
                  onChange={() => setStorage(!storage)}
                />
                <span className="slider" />
              </label>
            </div>
          </section>

        </div>
      </main>
    </PageWrapper>
  );
}