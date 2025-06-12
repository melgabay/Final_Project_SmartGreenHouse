import React, { useEffect, useState } from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';
import '../style/Dashboard.css';

export default function PlantGrowthGallery() {
  const [data, setData] = useState({});
  const [selectedPlant, setSelectedPlant] = useState(
    localStorage.getItem('selectedPlant') || ''
  );

  const getDiseaseName = (entry) =>
    entry?.disease_class?.name || entry?.deasese_class?.name || null;

  const getPixelSize = (entry) =>
    entry?.size_compare?.current_day_px ?? null;

  const fetchPlantData = async () => {
    try {
      const plantRes = await axios.get('http://localhost:5500/api/plant-data');
      const rawData = plantRes.data;

      const enrichedData = await Promise.all(
        Object.entries(rawData).map(async ([plantName, entries]) => {
          const entriesWithUrls = await Promise.all(
            entries.map(async (entry) => {
              if (!entry.file_name_image) return entry;
              const res = await axios.get(
                `http://localhost:5500/api/s3url?key=${entry.file_name_image}`
              );
              return { ...entry, image_url: res.data.url };
            })
          );

          entriesWithUrls.sort((a, b) => new Date(a.date) - new Date(b.date));

          const enriched = entriesWithUrls.map((entry, idx, arr) => {
            const disease = getDiseaseName(entry);
            const currentPx = getPixelSize(entry);
            if (!disease || currentPx == null) return { ...entry, dynamic_growth: null };

            const previousEntry = [...arr.slice(0, idx)]
              .reverse()
              .find((e) => getDiseaseName(e) === disease && getPixelSize(e) != null);

            if (!previousEntry) return { ...entry, dynamic_growth: null };

            const previousPx = getPixelSize(previousEntry);
            const diff = currentPx - previousPx;
            const percentage = previousPx ? (diff / previousPx) * 100 : 0;

            return {
              ...entry,
              dynamic_growth: { diff, percentage, previous_px: previousPx },
            };
          });

          return [plantName, enriched];
        })
      );

      setData(Object.fromEntries(enrichedData));
    } catch (err) {
      console.error('Error loading plant data and URLs:', err);
    }
  };

  useEffect(() => {
    fetchPlantData();
    const interval = setInterval(fetchPlantData, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleStorageChange = () =>
      setSelectedPlant(localStorage.getItem('selectedPlant') || '');
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const renderGrowthInfo = (entry) => {
    if (!entry.dynamic_growth) {
      return (
        <span className="text-gray">
          • <span className="badge gray">0%</span>
        </span>
      );
    }

    const { diff, percentage, previous_px } = entry.dynamic_growth;
    const currentPx = getPixelSize(entry);

    let colorClass = 'text-gray';
    let badgeClass = 'gray';
    let symbol = '•';

    if (diff > 0) {
      colorClass = 'text-green';
      badgeClass = 'green';
      symbol = '↑';
    } else if (diff < 0) {
      colorClass = 'text-red';
      badgeClass = 'red';
      symbol = '↓';
    }

    return (
      <span className={colorClass}>
        {symbol}{' '}
        <span className={`badge ${badgeClass}`}>
          {percentage >= 0 ? '+' : ''}
          {percentage.toFixed(1)}%
        </span>{' '}
        (from {previous_px.toLocaleString()} px to {currentPx.toLocaleString()} px)
      </span>
    );
  };

  const entries = data[selectedPlant] || [];
  const latestEntries = [...entries]
    .filter((entry) => entry.image_url)
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 10);

  return (
    <PageWrapper>
      <div className="p-6">
        <h1>Plant Growth</h1>
        <h2 className="text-2xl font-bold mb-6">
          {selectedPlant || 'No profile selected'}
        </h2>

        <div>
          {latestEntries.map((entry, idx) => (
            <div key={idx} className="card d-flex">
              <img
                src={entry.image_url}
                alt={`Plant ${idx}`}
                className="taille_affichee"
              />
              <p className="text-sm text-gray-600">
                <b>Date: {new Date(entry.date).toLocaleString()}</b>
              </p>
              <p className="text-sm">Growth: {renderGrowthInfo(entry)}</p>
              <p className="text-sm italic text-gray-500">
                Disease:{' '}
                {getDiseaseName(entry)
                  ?.replace(/_/g, ' ')
                  ?.replace(/\b\w/g, (l) => l.toUpperCase()) || '—'}
              </p>
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}