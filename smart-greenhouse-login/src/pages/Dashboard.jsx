import React, {useState, useEffect, useRef} from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';
import '../style/Dashboard.css';
import {
    LineChart, Line, XAxis, YAxis, Tooltip,
    ResponsiveContainer, CartesianGrid,
} from 'recharts';

export default function Dashboard() {
    const [sensorData, setSensorData] = useState({});
    const [series, setSeries] = useState({
        air_humidity: [],
        air_temperature_C: [],
        light_intensity: [],
        soil_humidity: [],
        soil_ph: [],
        soil_ec: [],
        soil_temp: [],
    });
    const [growthSeries, setGrowthSeries] = useState([]);
    const [latestSizePx, setLatestSizePx] = useState(null);
    const [actuators, setActuators] = useState({
        uv: 'OFF', irrigation: 'OFF', ventilation: 'OFF',
    });
    const [thresholds, setThresholds] = useState({
        uv: {on: '', off: '', paused: false},
        irrigation: {on: '', off: '', paused: false},
        ventilation: {on: '', off: '', paused: false},
    });
    const [editMode, setEditMode] = useState({
        uv: false, irrigation: false, ventilation: false,
    });
    const [modalImage, setModalImage] = useState(null);
    const [toast, setToast] = useState(false);
    const plantProfile = localStorage.getItem('selectedPlant') || 'No plant selected';
    const lastTsRef = useRef(null);
    const lastImageKeyRef = useRef(null);

    const SENSORS = [
        {key: 'air_humidity', label: 'Humidity', unit: '%'},
        {key: 'air_temperature_C', label: 'Temperature', unit: '°C'},
        {key: 'light_intensity', label: 'UV Light Intensity', unit: 'LUX'},
        {key: 'soil_humidity', label: 'Soil Moisture', unit: '%'},
        {key: 'soil_ph', label: 'Soil pH', unit: 'pH'},
        {key: 'soil_ec', label: 'Soil EC', unit: 'µS/cm'},
        {key: 'soil_temp', label: 'Soil Temperature', unit: '°C'},
    ];

    const fmtTimestamp = (ts) => {
        const d = new Date(ts);
        return `${d.toLocaleDateString()} at ${d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}`;
    };

    const pushActuators = async (payload) => {
        try {
            await axios.post('http://127.0.0.1:5500/api/update_actuators', payload);
        } catch (err) {
            console.error('Error updating actuators', err);
        }
    };
        const fetchLatest = async () => {
            try {
                const {data} = await axios.get('http://127.0.0.1:5500/api/latest-sensor');
                if (data.timestamp !== lastTsRef.current) {
                    lastTsRef.current = data.timestamp;
                    setSensorData(data);
                    setActuators({
                        uv: data.uv_light_on,          // valeurs déjà "ON" ou "OFF"
                        irrigation: data.irrigation_on,
                        ventilation: data.force_ventilation_on,
                    });
                    setThresholds({
                        uv: {
                            on: data.thresholds?.uv_light_on?.on ?? '',
                            off: data.thresholds?.uv_light_on?.off ?? '',
                            paused: data.mode?.uv_light_on === 'MANUAL'
                        },
                        irrigation: {
                            on: data.thresholds?.irrigation_on?.on ?? '',
                            off: data.thresholds?.irrigation_on?.off ?? '',
                            paused: data.mode?.irrigation_on === 'MANUAL'
                        },
                        ventilation: {
                            on: data.thresholds?.force_ventilation_on?.on ?? '',
                            off: data.thresholds?.force_ventilation_on?.off ?? '',
                            paused: data.mode?.force_ventilation_on === 'MANUAL'
                        }
                    });
                }
            } catch (err) {
                console.error('Error fetching latest sensor', err);
            }
        };

const saveActuator = async (key) => {
  const payload = {
    // STATES
    uv_light_on:           actuators.uv,
    irrigation_on:         actuators.irrigation,
    force_ventilation_on:  actuators.ventilation,
    // MODE
    uv_light_on_manual:            thresholds.uv.paused,
    irrigation_on_manual:          thresholds.irrigation.paused,
    force_ventilation_on_manual:   thresholds.ventilation.paused,
    // THRESHOLDS
    uv_light_on_on:                thresholds.uv.on,
    uv_light_on_off:               thresholds.uv.off,
    irrigation_on_on:              thresholds.irrigation.on,
    irrigation_on_off:             thresholds.irrigation.off,
    force_ventilation_on_on:       thresholds.ventilation.on,
    force_ventilation_on_off:      thresholds.ventilation.off,
  };

  try {
    await pushActuators(payload);   // POST
    await fetchLatest();            // ← mise à jour immédiate
    setToast(true);                 // affiche le toast
    setTimeout(() => setToast(false), 2500);  // disparaît après 2,5 s
  } catch (err) {
    console.error(err);
  }

  setEditMode((prev) => ({ ...prev, [key]: false }));
};
    const cancelEdit = (key) => {
        setEditMode((prev) => ({...prev, [key]: false}));
    };

    useEffect(() => {

        const fetchSeries = async () => {
            for (const {key} of SENSORS) {
                try {
                    const {data} = await axios.get(`http://127.0.0.1:5500/api/history/${key}?limit=180`);
                    setSeries((prev) => ({...prev, [key]: data}));
                } catch (err) {
                    console.error(`Error fetching ${key} history`, err);
                }
            }
        };

        const fetchGrowth = async () => {
            if (plantProfile === 'No plant selected') return;
            try {
                const {data} = await axios.get(`http://127.0.0.1:5500/api/growth/${plantProfile}?limit=30`);
                setGrowthSeries(data);
                if (data.length > 0) {
                    const latest = data[data.length - 1];
                    setLatestSizePx(latest.current_px);
                }
            } catch (err) {
                console.error('Error fetching growth data', err);
            }
        };

        const checkNewImage = async () => {
            try {
                const {data} = await axios.get('http://127.0.0.1:5500/api/latest-image-key');
                const latestKey = data.key;

                if (latestKey && latestKey !== lastImageKeyRef.current) {
                    lastImageKeyRef.current = latestKey;
                    await axios.post('http://127.0.0.1:5500/api/process-latest');
                }
            } catch (err) {
                console.error('Image detection error:', err);
            }
        };

        fetchLatest();
        fetchSeries();
        fetchGrowth();
        const intervalId = setInterval(() => {
            fetchLatest();
            fetchSeries();
            fetchGrowth();
            checkNewImage();
        }, 10_000);

        return () => clearInterval(intervalId);
    }, [plantProfile]);

    const renderSensorChart = (key) => {
        const sensor = SENSORS.find(s => s.key === key);
        const label = `${sensor?.label} (${sensor?.unit})`;

        return (
            <ResponsiveContainer width="100%" height={200}>
                <LineChart data={series[key]}>
                    <CartesianGrid strokeDasharray="3 3"/>
                    <XAxis
                        dataKey="timestamp"
                        tickFormatter={(t) => {
                            const d = new Date(t);
                            const day = String(d.getDate()).padStart(2, '0');
                            const month = String(d.getMonth() + 1).padStart(2, '0');
                            return `${day}/${month}`;
                        }}
                        label={{value: 'Date', position: 'outsideRight', offset: 10, dx: 280, dy: 14.5}}
                    />
                    <YAxis
                        label={{value: label, angle: -90, position: 'outsideLeft', offset: 10, dx: -20, dy: 15}}
                    />
                    <Tooltip labelFormatter={(l) => new Date(l).toLocaleString()}/>
                    <Line type="monotone" dataKey="value" stroke="#8884d8" dot={false}/>
                </LineChart>
            </ResponsiveContainer>
        );
    };

    const renderGrowthChart = () => (
        <ResponsiveContainer width="100%" height={200}>
            <LineChart data={growthSeries}>
                <CartesianGrid strokeDasharray="3 3"/>
                <XAxis
                    dataKey="timestamp"
                    tickFormatter={(t) => {
                        const d = new Date(t);
                        const day = String(d.getDate()).padStart(2, '0');
                        const month = String(d.getMonth() + 1).padStart(2, '0');
                        return `${day}/${month}`;
                    }}
                    label={{value: 'Date', position: 'insideBottomRight', offset: -5}}
                />
                <YAxis
                    tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                    label={{value: 'Size (px)', angle: -90, position: 'outsideLeft', offset: 10, dx: -25, dy: 50}}
                />
                <Tooltip labelFormatter={(l) => new Date(l).toLocaleString()}/>
                <Line type="monotone" dataKey="current_px" stroke="#82ca9d" dot={false}/>
            </LineChart>
        </ResponsiveContainer>
    );

    const formattedTimestamp = sensorData?.timestamp ? fmtTimestamp(sensorData.timestamp) : '';

    return (
        <PageWrapper>
            <h1>Dashboard</h1>
            <div className="row">
                <section className="col-md-8">
                    <h2>Live Data</h2>
                    {formattedTimestamp && <div className="card"><b>Date:</b> {formattedTimestamp}</div>}

                    {SENSORS.map(({key, label, unit}) => {
                        const val = sensorData?.[key];
                        if (val === undefined) return null;
                        return (
                            <div className="card" key={key}>
                                <b>{label}: {parseFloat(val).toFixed(1)} {unit}</b>
                                <div className="mt-2">{renderSensorChart(key)}</div>
                            </div>
                        );
                    })}

                    {growthSeries.length > 0 && (
                        <div className="card">
                            <b>Current Size: {latestSizePx ?? '—'} px</b>
                            <div className="mt-2">{renderGrowthChart()}</div>
                        </div>
                    )}
                </section>

                <section className="actuators">
                    <h2>Actuators</h2>
                    {['uv', 'irrigation', 'ventilation'].map((key) => {
                        const labels = {
                            uv: 'UV Light',
                            irrigation: 'Soil Moisture',
                            ventilation: 'Air Temperature'
                        };

                        return (
                            <div className="card" key={key}>
                                <b>{labels[key]}</b>
                                <span
                                    className={`status ${actuators[key] === 'ON' ? 'on' : 'off'}`}>{actuators[key]}</span>

                                <div className="form-check">
                                    <input type="checkbox" className="form-check-input" checked={thresholds[key].paused}
                                           onChange={(e) => setThresholds((p) => ({
                                               ...p,
                                               [key]: {...p[key], paused: e.target.checked}
                                           }))} id={`pause-${key}`}/>
                                    <label className="form-check-label" htmlFor={`pause-${key}`}>Manual mode</label>
                                </div>

                                {!editMode[key] ? (
                                    <>
                                        <div className="threshold-view mt-1">
                                            {thresholds[key].paused ? (
                                                <small className="text-muted">Paused</small>
                                            ) : (
                                                <>
                                                    <small>If {labels[key]} ≥ {thresholds[key].on || '—'} then
                                                        ON</small><br/>
                                                    <small>If {labels[key]} ≤ {thresholds[key].off || '—'} then
                                                        OFF</small>
                                                </>
                                            )}
                                        </div>
                                        <button className="action-button mt-2"
                                                onClick={() => setEditMode((p) => ({...p, [key]: true}))}>Modify
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        {thresholds[key].paused ? (
                                            <div className="d-flex gap-2 mt-2">
                                                <button
                                                    className={`action-button ${actuators[key] === 'ON' ? 'on' : ''}`}
                                                    onClick={() => setActuators((p) => ({...p, [key]: 'ON'}))}>ON
                                                </button>
                                                <button
                                                    className={`action-button ${actuators[key] === 'OFF' ? 'off' : ''}`}
                                                    onClick={() => setActuators((p) => ({...p, [key]: 'OFF'}))}>OFF
                                                </button>
                                            </div>
                                        ) : (
                                            <div className="d-flex gap-2 mt-2">
                                                <input type="number" className="form-control" placeholder="ON value"
                                                       value={thresholds[key].on}
                                                       onChange={(e) => setThresholds((p) => ({
                                                           ...p,
                                                           [key]: {...p[key], on: e.target.value}
                                                       }))}/>
                                                <input type="number" className="form-control" placeholder="OFF value"
                                                       value={thresholds[key].off}
                                                       onChange={(e) => setThresholds((p) => ({
                                                           ...p,
                                                           [key]: {...p[key], off: e.target.value}
                                                       }))}/>
                                            </div>
                                        )}

                                        <div className="mt-2">
                                            <button className="action-button me-2"
                                                    onClick={() => saveActuator(key)}>Save
                                            </button>
                                            <button className="action-button secondary"
                                                    onClick={() => cancelEdit(key)}>Cancel
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        );
                    })}
                </section>
            </div>

            {modalImage && (
                <div className="modal-overlay" onClick={() => setModalImage(null)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <img src={modalImage} alt="Zoomed" className="modal-image"/>
                        <button className="close-button" onClick={() => setModalImage(null)}>×</button>
                    </div>
                </div>
            )}
            {toast && (
  <div className="toast-container position-fixed bottom-0 end-0 p-3" style={{ zIndex: 9999 }}>
    <div className="toast show" role="alert">
      <div className="toast-body">
        Saved
      </div>
    </div>
  </div>
)}
        </PageWrapper>
    );
}