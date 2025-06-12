import React, {useState, useEffect, useRef} from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';
import '../style/Dashboard.css';
import {
    LineChart, Line, XAxis, YAxis, Tooltip,
    ResponsiveContainer, CartesianGrid,
} from 'recharts';

export default function Dashboard() {
    // ───── State ─────
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
        uv: {on: '', off: ''},
        irrigation: {on: '', off: ''},
        ventilation: {on: '', off: ''},
    });
    const [editMode, setEditMode] = useState({
        uv: false, irrigation: false, ventilation: false,
    });

    const [modalImage, setModalImage] = useState(null);
    const plantProfile = localStorage.getItem('selectedPlant') || 'No plant selected';
    const lastTsRef = useRef(null);
    const lastImageKeyRef = useRef(null);

    // ───── Sensor Mapping ─────
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

    const saveActuator = (key) => {
        const payload = {
            uv_light_on: actuators.uv,
            irrigation_on: actuators.irrigation,
            force_ventilation_on: actuators.ventilation,
            uv_on_value: thresholds.uv.on,
            uv_off_value: thresholds.uv.off,
            irrigation_on_value: thresholds.irrigation.on,
            irrigation_off_value: thresholds.irrigation.off,
            force_ventilation_on_value: thresholds.ventilation.on,
            force_ventilation_off_value: thresholds.ventilation.off,
        };
        pushActuators(payload);
        setEditMode((prev) => ({...prev, [key]: false}));
    };

    const cancelEdit = (key) => {
        setEditMode((prev) => ({...prev, [key]: false}));
    };

    // ───── Fetch Data ─────
    useEffect(() => {
        const fetchLatest = async () => {
            try {
                const {data} = await axios.get('http://127.0.0.1:5500/api/latest-sensor');
                if (data.timestamp !== lastTsRef.current) {
                    lastTsRef.current = data.timestamp;
                    setSensorData(data);
                    setActuators({
                        uv: data.uv_light_on ? 'ON' : 'OFF',
                        irrigation: data.irrigation_on ? 'ON' : 'OFF',
                        ventilation: data.force_ventilation_on ? 'ON' : 'OFF',
                    });
                    setThresholds({
                        uv: {on: data.uv_on_value ?? '', off: data.uv_off_value ?? ''},
                        irrigation: {on: data.irrigation_on_value ?? '', off: data.irrigation_off_value ?? ''},
                        ventilation: {
                            on: data.force_ventilation_on_value ?? '',
                            off: data.force_ventilation_off_value ?? ''
                        },
                    });
                }
            } catch (err) {
                console.error('Error fetching latest sensor', err);
            }
        };

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
                    const res = await axios.post('http://127.0.0.1:5500/api/process-latest');
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

    // ───── Chart Renderers ─────
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

    // ───── Render ─────
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
                            irrigation: 'Irrigation',
                            ventilation: 'Ventilation'
                        };

                        return (
                            <div className="card" key={key}>
                                <b>{labels[key]}</b>
                                <span className={`status ${actuators[key] === 'ON' ? 'on' : 'off'}`}>
                                    {actuators[key]}
                                </span>

                                {!editMode[key] ? (
                                    <>
                                        <div className="threshold-view mt-1">
                                            <small>ON ≥ {thresholds[key].on || '—'}</small><br/>
                                            <small>OFF ≤ {thresholds[key].off || '—'}</small>
                                        </div>
                                        <button className="action-button mt-2"
                                                onClick={() => setEditMode((p) => ({...p, [key]: true}))}>
                                            Modify
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <select className="form-select mt-2" value={actuators[key]}
                                                onChange={(e) => setActuators((p) => ({...p, [key]: e.target.value}))}>
                                            <option value="ON">ON</option>
                                            <option value="OFF">OFF</option>
                                        </select>
                                        <div className="d-flex gap-2 mt-2">
                                            <input type="number" className="form-control" placeholder="ON value"
                                                   value={thresholds[key].on} onChange={(e) => setThresholds((p) => ({
                                                ...p,
                                                [key]: {...p[key], on: e.target.value}
                                            }))}/>
                                            <input type="number" className="form-control" placeholder="OFF value"
                                                   value={thresholds[key].off} onChange={(e) => setThresholds((p) => ({
                                                ...p,
                                                [key]: {...p[key], off: e.target.value}
                                            }))}/>
                                        </div>
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
        </PageWrapper>
    );
}