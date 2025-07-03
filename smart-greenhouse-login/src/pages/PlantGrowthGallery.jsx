import React, { useEffect, useState } from "react";
import axios from "axios";
import PageWrapper from "../component/PageWrapper";
import "../style/Dashboard.css";

export default function PlantGrowthGallery() {
  const [plantData, setPlantData] = useState([]);
  const [selectedPlant, setSelectedPlant] = useState(
    localStorage.getItem("selectedPlant") || ""
  );

  /* ───────────── Helpers ───────────── */

  const getDiseaseName = (entry) => entry?.disease_class?.name ?? null;
  const getPixelSize   = (entry) => entry?.current_day_px ?? null;

  /* ───────────── Fetch + transform ───────────── */

  const fetchPlantData = async () => {
    try {
      const { data: raw } = await axios.get(
        "http://localhost:5500/api/plant-data"
      );

      // ── Déplie tous les blocs en images individuelles (rétro-compatible) ──
      const imagesFlat = await Promise.all(
        Object.entries(raw).flatMap(([plantName, blocks]) =>
          blocks.flatMap((block) => {
            // En JSON v2, block.images existe; en v1 non
            const imgsArray =
              Array.isArray(block.images) && block.images.length
                ? block.images
                : [block]; // v1 : le bloc EST l’image

            return imgsArray.map(async (img) => {
              // URL signée S3
              const {
                data: { url },
              } = await axios.get(
                `http://localhost:5500/api/s3url?key=${img.file_name_image}`
              );

              return {
                ...img,
                plant_name  : plantName,
                disease_class: block.disease_class ?? img.disease_class,
                global_current_px: block.global_current_px ?? img.global_current_px,
                difference_global_growth: block.difference_global_growth ?? img.difference_global_growth,
                image_url: url,
              };
            });
          })
        )
      );

      // ── Tri ascendant (plus ancien → plus récent) ──
      imagesFlat.sort((a, b) => new Date(a.date) - new Date(b.date));

      /* Ajout d’un champ dynamic_growth basé sur l’ordre chronologique
         (pour préserver l’affichage flèche ↑ / ↓ / •) */
      const lastPxByPlant = {};
      const enriched = imagesFlat.map((entry) => {
        const currentPx = getPixelSize(entry);
        const lastPx    = lastPxByPlant[entry.plant_name] ?? null;

        let growthInfo;
        if (currentPx == null) {
          growthInfo = null;
        } else if (lastPx == null) {
          growthInfo = { previous_px: null }; // première image
        } else {
          const diff       = currentPx - lastPx;
          const percentage = lastPx ? (diff / lastPx) * 100 : 0;
          growthInfo = { diff, percentage, previous_px: lastPx };
        }

        lastPxByPlant[entry.plant_name] = currentPx;
        return { ...entry, dynamic_growth: growthInfo };
      });

      setPlantData(enriched);
    } catch (err) {
      console.error("Error loading plant data and URLs:", err);
    }
  };

  /* ───────────── Effects ───────────── */

  useEffect(() => {
    fetchPlantData();
    const interval = setInterval(fetchPlantData, 10000);
    return () => clearInterval(interval);
  }, []);

  /* ───────────── Render helpers ───────────── */

  const renderGrowthInfo = (entry) => {
    // priorité : valeurs calculées côté backend
    const backendDiff = entry.growth;
    const backendPct  = entry.growth_pourcentage;

    const useBackend =
      backendDiff !== undefined &&
      backendPct  !== undefined &&
      backendPct  !== null;

    if (useBackend) {
      if (backendDiff === 0) {
        return (
          <span className="text-gray">
            • <span className="badge gray">0.0%</span>
          </span>
        );
      }
      const isIncrease = backendDiff > 0;
      const color = isIncrease ? "green" : "red";
      const icon  = isIncrease ? "↑" : "↓";
      return (
        <span className={`text-${color}`}>
          {icon}{" "}
          <span className={`badge ${color}`}>
            {backendPct.toFixed(1)}%
          </span>
        </span>
      );
    }

    // fallback : calcul dynamique côté front
    if (!entry.dynamic_growth || entry.dynamic_growth.previous_px == null) {
      return <span className="text-blue-500 font-semibold">Initial</span>;
    }

    const { diff, percentage, previous_px } = entry.dynamic_growth;
    const currentPx = getPixelSize(entry);
    const isIncrease = diff > 0;
    const isEqual    = diff === 0;
    const icon  = isEqual ? "•" : isIncrease ? "↑" : "↓";
    const color = isEqual ? "gray" : isIncrease ? "green" : "red";

    return (
      <span className={`text-${color}`}>
        {icon}{" "}
        <span className={`badge ${color}`}>{percentage.toFixed(1)}%</span>{" "}
        (from {previous_px?.toLocaleString()} px to{" "}
        {currentPx?.toLocaleString()} px)
      </span>
    );
  };

  /* ───────────── Filtrage + tri pour l’affichage ───────────── */

  const filteredEntries = [...plantData]
    .filter(
      (e) => e.image_url && (!selectedPlant || e.plant_name === selectedPlant)
    )
    .sort((a, b) => new Date(b.date) - new Date(a.date))
    .slice(0, 30);

  /* ───────────── JSX ───────────── */

  return (
    <PageWrapper>
      <div className="p-6">
        <h1>Plant Growth</h1>
        <h2 className="text-2xl font-bold mb-6">
          {selectedPlant || "All Plants"}
        </h2>

        <div className="grid-container">
          {filteredEntries.map((entry, idx) => (
            <div key={idx} className="card growning">
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
                Disease:{" "}
                {getDiseaseName(entry)
                  ?.replace(/_/g, " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase()) || "—"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </PageWrapper>
  );
}