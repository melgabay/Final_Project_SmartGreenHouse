import React, { useEffect, useState } from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';
import '../style/Dashboard.css';

export default function PlantGrowthGallery() {
  const [plantData, setPlantData] = useState([]);
  const [selectedPlant, setSelectedPlant] = useState(localStorage.getItem('selectedPlant') || '');

  const getDiseaseName = (entry) =>
    entry?.disease_class?.name || entry?.deasese_class?.name || null;

  const getPixelSize = (entry) =>
    entry?.size_compare?.current_day_px ?? null;

const fetchPlantData = async () => {
  try {
    const res = await axios.get('http://localhost:5500/api/plant-data');
    const rawData = res.data;

    const enrichedData = await Promise.all(
      Object.entries(rawData).map(async ([plantName, entries]) => {
        const entriesWithUrls = await Promise.all(
          entries.map(async (entry) => {
            if (!entry.file_name_image) return entry;
            const res = await axios.get(`http://localhost:5500/api/s3url?key=${entry.file_name_image}`);
            return { ...entry, image_url: res.data.url };
          })
        );

        // Tri par date croissante
        entriesWithUrls.sort((a, b) => new Date(a.date) - new Date(b.date));

        let lastPx = null;

        const enriched = entriesWithUrls.map((entry) => {
          const currentPx = getPixelSize(entry);
          const disease = getDiseaseName(entry);

          if (currentPx == null) {
            return { ...entry, dynamic_growth: null, plant_name: plantName };
          }

          let growthInfo = null;

          if (lastPx != null) {
            const diff = currentPx - lastPx;
            const percentage = lastPx ? (diff / lastPx) * 100 : 0;
            growthInfo = { diff, percentage, previous_px: lastPx };
          } else {
            growthInfo = { previous_px: null }; // première image
          }

          lastPx = currentPx; // met à jour pour le prochain
          return {
            ...entry,
            dynamic_growth: growthInfo,
            plant_name: plantName
          };
        });

        return enriched;
      })
    );

    const flattened = enrichedData.flat();
    setPlantData(flattened);
  } catch (err) {
    console.error('Error loading plant data and URLs:', err);
  }
};
  useEffect(() => {
    fetchPlantData();
    const interval = setInterval(fetchPlantData, 10000);
    return () => clearInterval(interval);
  }, []);

  const renderGrowthInfo = (entry) => {
    if (!entry.dynamic_growth || entry.dynamic_growth.previous_px == null) {
      return <span className="text-blue-500 font-semibold">Initial</span>;
    }

    const { diff, percentage, previous_px } = entry.dynamic_growth;
    const currentPx = getPixelSize(entry);
    const isIncrease = diff > 0;
    const isEqual = diff === 0;
    const icon = isEqual ? '•' : isIncrease ? '↑' : '↓';
    const color = isEqual ? 'gray' : isIncrease ? 'green' : 'red';

    return (
      <span className={`text-${color}`}>
        {icon} <span className={`badge ${color}`}>{percentage.toFixed(1)}%</span> (from {previous_px.toLocaleString()} px to {currentPx.toLocaleString()} px)
      </span>
    );
  };

  const filteredEntries = [...plantData]
    .filter((e) => e.image_url && (!selectedPlant || e.plant_name === selectedPlant))
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 30); // ajustable

  return (
    <PageWrapper>
      <div className="p-6">
        <h1>Plant Growth</h1>
        <h2 className="text-2xl font-bold mb-6">{selectedPlant || 'All Plants'}</h2>
        <div className="grid-container">
          {filteredEntries.map((entry, idx) => (
            <div key={idx} className="card growning">
              <img src={entry.image_url} alt={`Plant ${idx}`} className="taille_affichee" />
              <p className="text-sm text-gray-600">
                <b>Date: {new Date(entry.date).toLocaleString()}</b>
              </p>
              <p className="text-sm">Growth: {renderGrowthInfo(entry)}</p>
              <p className="text-sm italic text-gray-500">
                Disease: {getDiseaseName(entry)?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) || '—'}
              </p>
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}