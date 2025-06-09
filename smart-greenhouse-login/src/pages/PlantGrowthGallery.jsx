import React, { useEffect, useState } from 'react';
import axios from 'axios';
import PageWrapper from '../component/PageWrapper';

export default function PlantGrowthGallery() {
  const [data, setData] = useState({});
  const [selectedPlant, setSelectedPlant] = useState(localStorage.getItem('selectedPlant') || '');

  // Fetch plant data and enrich with S3 image URLs + dynamic growth
  useEffect(() => {
    const fetchPlantData = async () => {
      try {
        const plantRes = await axios.get('http://localhost:5500/api/plant-data');
        const rawData = plantRes.data;

        const dataWithUrls = await Promise.all(
          Object.entries(rawData).map(async ([plantName, entries]) => {
            const entriesWithUrls = await Promise.all(
              entries.map(async (entry) => {
                if (!entry.file_name_image) return entry;
                const urlRes = await axios.get(`http://localhost:5500/api/s3url?key=${entry.file_name_image}`);
                return { ...entry, image_url: urlRes.data.url };
              })
            );

            // Sort entries by ascending date
            entriesWithUrls.sort((a, b) => new Date(a.date) - new Date(b.date));

            // Add dynamic growth info per disease class
            const enriched = entriesWithUrls.map((entry, idx, arr) => {
              const currentDisease = entry.deasese_class.name;
              const currentPx = entry.size_compare.current_day_px;

              const prevEntry = [...arr.slice(0, idx)].reverse().find(e =>
                e.deasese_class.name === currentDisease
              );

              if (!prevEntry) {
                return { ...entry, dynamic_growth: null };
              }

              const prevPx = prevEntry.size_compare.current_day_px;
              const diff = currentPx - prevPx;
              const percentage = (diff / prevPx) * 100;

              return {
                ...entry,
                dynamic_growth: {
                  diff,
                  percentage,
                  previous_px: prevPx
                }
              };
            });

            return [plantName, enriched];
          })
        );

        setData(Object.fromEntries(dataWithUrls));
      } catch (err) {
        console.error('Error loading plant data and URLs:', err);
      }
    };

    fetchPlantData();
  }, []);

  // Monitor localStorage for profile changes
  useEffect(() => {
    const interval = setInterval(() => {
      const current = localStorage.getItem('selectedPlant');
      if (current !== selectedPlant) {
        setSelectedPlant(current);
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [selectedPlant]);

  // Render dynamic growth info block
  const renderGrowthInfo = (entry) => {
    if (!entry.dynamic_growth) {
      return <span className="text-gray-500">Initial state</span>;
    }

    const { diff, percentage, previous_px } = entry.dynamic_growth;
    const now = entry.size_compare.current_day_px;
    const direction = diff > 0 ? 'increase' : 'decrease';
    const color = diff > 0 ? 'text-green-600' : 'text-red-600';

    return (
      <span className={color}>
        {direction} – {Math.abs(diff).toLocaleString()} px <br />
        (Initial: {previous_px.toLocaleString()} px → Now: {now.toLocaleString()} px | {percentage >= 0 ? '+' : ''}{percentage.toFixed(1)}%)
      </span>
    );
  };

  const entries = data[selectedPlant] || [];
  const sorted = [...entries]
    .filter(entry => entry.image_url)
    .sort((a, b) => new Date(b.date) - new Date(a.date)) // show newest first
    .slice(0, 10); // limit to 10 entries

  return (
    <PageWrapper>
      <div className="p-6">
        <h1>Growth Plants</h1>
        <h2 className="text-2xl font-bold mb-6">{selectedPlant || 'No profile selected'}</h2>
        <div>
          {sorted.map((img, idx) => (
            <div key={idx} className="card d-flex">
              <img
                src={img.image_url}
                alt={`Plant ${idx}`}
                className="taille_affichee"
              />
              <p className="text-sm text-gray-600">
                Date: {new Date(img.date).toLocaleString()}
              </p>
              <p className="text-sm">
                Growth: {renderGrowthInfo(img)}
              </p>
              <p className="text-sm italic text-gray-500">
                Disease: {img.deasese_class.name.replace(/_/g, ' ')}
              </p>
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}