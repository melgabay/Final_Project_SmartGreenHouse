import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';
import '../style/Dashboard.css';
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts';

/**
 * Dashboard.jsx – actuators + seuils ON/OFF
 * -----------------------------------------
 * • Modify → ON/OFF + saisie des seuils → Save (POST /api/update_actuators)
 * • Le backend renvoie ces champs via /api/latest-sensor pour pré-remplir.
 */
export default function Dashboard() {
  /* ────── state ────── */
  const [sensorData, setSensorData] = useState({});
  const [modalImage, setModalImage] = useState(null);
  const [series, setSeries] = useState({
    air_humidity: [], air_temperature_C: [], light_intensity: [], soil_humidity: [],
  });
  const [growthSeries, setGrowthSeries] = useState([]);

  /* ON / OFF */
  const [actuators, setActuators] = useState({
    uv: 'OFF', irrigation: 'OFF', ventilation: 'OFF',
  });

  /* Seuils */
  const [thresholds, setThresholds] = useState({
    uv:          { on: '', off: '' },
    irrigation:  { on: '', off: '' },
    ventilation: { on: '', off: '' },
  });

  /* carte en édition ? */
  const [editMode, setEditMode] = useState({
    uv: false, irrigation: false, ventilation: false,
  });

  const lastTsRef   = useRef(null);
  const plantProfile = localStorage.getItem('selectedPlant') || 'No plant selected';

  const VALID_SENSORS = [
    { key: 'air_humidity',      label: 'Humidity' },
    { key: 'air_temperature_C', label: 'Temperature' },
    { key: 'light_intensity',   label: 'UV Light' },
    { key: 'soil_humidity',     label: 'Soil Moisture' },
  ];

  const KEY_MAP = {
    uv: 'uv_light_on',
    irrigation: 'irrigation_on',
    ventilation: 'force_ventilation_on',
  };

  /* ───── helpers ───── */
  const fmt = (ts) => {
    const d = new Date(ts);
    return `${d.toLocaleDateString()} at ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  };

  /* ───── API helpers ───── */
  const pushActuators = async (payload) => {
    try { await axios.post('http://127.0.0.1:5500/api/update_actuators', payload); }
    catch (err) { console.error('Error updating actuators', err); }
  };

  const saveActuator = (key) => {
    /* construit le payload complet */
    const payload = {
      uv_light_on:                  actuators.uv,
      irrigation_on:                actuators.irrigation,
      force_ventilation_on:         actuators.ventilation,

      uv_on_value:                  thresholds.uv.on,
      uv_off_value:                 thresholds.uv.off,
      irrigation_on_value:          thresholds.irrigation.on,
      irrigation_off_value:         thresholds.irrigation.off,
      force_ventilation_on_value:   thresholds.ventilation.on,
      force_ventilation_off_value:  thresholds.ventilation.off,
    };
    pushActuators(payload);
    setEditMode((p) => ({ ...p, [key]: false }));
  };

  const cancelEdit = (key) => {
    /* repasse en lecture sans toucher aux valeurs */
    setEditMode((p) => ({ ...p, [key]: false }));
  };

  /* ───── fetch ───── */
  useEffect(() => {
    const fetchLatest = async () => {
      try {
        const { data } = await axios.get('http://127.0.0.1:5500/api/latest-sensor');
        if (data.timestamp !== lastTsRef.current) {
          lastTsRef.current = data.timestamp;
          setSensorData(data);

          /* ON / OFF */
          setActuators({
            uv:          data.uv_light_on           ? 'ON' : 'OFF',
            irrigation:  data.irrigation_on        ? 'ON' : 'OFF',
            ventilation: data.force_ventilation_on ? 'ON' : 'OFF',
          });

          /* Seuils */
          setThresholds({
            uv: {
              on:  data.uv_on_value  ?? '',
              off: data.uv_off_value ?? '',
            },
            irrigation: {
              on:  data.irrigation_on_value  ?? '',
              off: data.irrigation_off_value ?? '',
            },
            ventilation: {
              on:  data.force_ventilation_on_value  ?? '',
              off: data.force_ventilation_off_value ?? '',
            },
          });
        }
      } catch (err) { console.error('Error fetching latest sensor', err); }
    };

    const fetchSeries = async () => {
      for (const { key } of VALID_SENSORS) {
        try {
          const { data } = await axios.get(`http://127.0.0.1:5500/api/history/${key}?limit=180`);
          setSeries((prev) => ({ ...prev, [key]: data }));
        } catch (err) { console.error('Error fetching history', key, err); }
      }
    };

    const fetchGrowth = async () => {
      if (plantProfile === 'No plant selected') return;
      try {
        const { data } = await axios.get(`http://127.0.0.1:5500/api/growth/${plantProfile}?limit=30`);
        setGrowthSeries(data);
      } catch (err) { console.error('Error fetching growth', err); }
    };

    fetchLatest(); fetchSeries(); fetchGrowth();
    const id = setInterval(() => { fetchLatest(); fetchSeries(); fetchGrowth(); }, 10_000);
    return () => clearInterval(id);
  }, [plantProfile]);

  /* ───── charts ───── */
  const chart = (k) => (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={series[k]}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp"
               tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}/>
        <YAxis/>
        <Tooltip labelFormatter={(l) => new Date(l).toLocaleString()}/>
        <Line type="monotone" dataKey="value" stroke="#8884d8" dot={false}/>
      </LineChart>
    </ResponsiveContainer>
  );

  const growthChart = () => (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={growthSeries}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" tickFormatter={(t) => new Date(t).toLocaleDateString()}/>
        <YAxis/>
        <Tooltip labelFormatter={(l) => new Date(l).toLocaleString()}/>
        <Line type="monotone" dataKey="current_px" stroke="#82ca9d" dot={false}/>
      </LineChart>
    </ResponsiveContainer>
  );

  /* ───── render ───── */
  const formatted = sensorData?.timestamp ? fmt(sensorData.timestamp) : '';

  return (
    <PageWrapper>
      <>
        <h1>Dashboard</h1>
        <div className="row">
          {/* gauche – mesures + graphes */}
          <section className="col-md-8">
            <h2 className="d-block">Live Data</h2>
            {formatted && <div className="card d-block"><b>Date:</b> {formatted}</div>}

            {VALID_SENSORS.map(({ key, label }) => {
              const v = sensorData?.[key];
              if (v === undefined) return null;
              return (
                <div className="card d-block" key={key}>
                  <b>{label}</b>: {parseFloat(v).toFixed(1)}
                  <div className="mt-2">{chart(key)}</div>
                </div>
              );
            })}

            {growthSeries.length > 0 && (
              <div className="card d-block">
                <b>Growth</b>
                <div className="mt-2">{growthChart()}</div>
              </div>
            )}
          </section>

          {/* droite – actuators */}
          <section className="actuators">
            <h2>Actuators</h2>
            {['uv', 'irrigation', 'ventilation'].map((key) => {
              const labelMap = { uv: 'UV Light', irrigation: 'Irrigation', ventilation: 'Ventilation' };
              return (
                <div className="card" key={key}>
                  <b>{labelMap[key]}</b>
                  <span className={`status ${actuators[key] === 'ON' ? 'on' : 'off'}`}>
                    {actuators[key]}
                  </span>

                  {/* affichage des seuils */}
                  {!editMode[key] && (
                    <div className="threshold-view mt-1">
                      <small>ON ≥ {thresholds[key].on || '—'}</small><br/>
                      <small>OFF ≤ {thresholds[key].off || '—'}</small>
                    </div>
                  )}

                  {editMode[key] ? (
                    <>
                      {/* select ON/OFF */}
                      <select
                        className="form-select mt-2"
                        value={actuators[key]}
                        onChange={(e) =>
                          setActuators((p) => ({ ...p, [key]: e.target.value }))
                        }
                      >
                        <option value="ON">ON</option>
                        <option value="OFF">OFF</option>
                      </select>

                      {/* seuils */}
                      <div className="d-flex gap-2 mt-2">
                        <input
                          type="number"
                          className="form-control"
                          placeholder="ON value"
                          value={thresholds[key].on}
                          onChange={(e) =>
                            setThresholds((p) => ({
                              ...p,
                              [key]: { ...p[key], on: e.target.value },
                            }))
                          }
                        />
                        <input
                          type="number"
                          className="form-control"
                          placeholder="OFF value"
                          value={thresholds[key].off}
                          onChange={(e) =>
                            setThresholds((p) => ({
                              ...p,
                              [key]: { ...p[key], off: e.target.value },
                            }))
                          }
                        />
                      </div>

                      <div className="mt-2">
                        <button className="action-button me-2" onClick={() => saveActuator(key)}>Save</button>
                        <button className="action-button secondary" onClick={() => cancelEdit(key)}>Cancel</button>
                      </div>
                    </>
                  ) : (
                    <button
                      className="action-button mt-2"
                      onClick={() => setEditMode((p) => ({ ...p, [key]: true }))}
                    >
                      Modify
                    </button>
                  )}
                </div>
              );
            })}
          </section>
        </div>

        {/* modal zoom image */}
        {modalImage && (
          <div className="modal-overlay" onClick={() => setModalImage(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <img src={modalImage} alt="Zoomed Graph" className="modal-image" />
              <button className="close-button" onClick={() => setModalImage(null)}>✕</button>
            </div>
          </div>
        )}
      </>
    </PageWrapper>
  );
}