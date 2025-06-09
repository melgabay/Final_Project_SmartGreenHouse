require('dotenv').config();
const express = require('express');
const AWS = require('aws-sdk');
const cors = require('cors');

const app = express();
const port = process.env.PORT || 5500;

app.use(cors());

// S3 Configuration
const s3 = new AWS.S3({
  region: process.env.AWS_REGION,
  accessKeyId: process.env.AWS_ACCESS_KEY_ID,
  secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
});

// Generate a signed URL to access an image (if needed)
app.get('/api/s3url', (req, res) => {
  const key = req.query.key;
  if (!key) return res.status(400).json({ error: 'Missing key parameter' });

  const params = {
    Bucket: process.env.AWS_BUCKET_NAME,
    Key: key,
    Expires: 60 * 5,
  };

  try {
    const url = s3.getSignedUrl('getObject', params);
    res.json({ url });
  } catch (err) {
    console.error("Error generating signed URL:", err);
    res.status(500).json({ error: 'Failed to generate signed URL' });
  }
});

// Retrieve ALL sensor data (complete history)
app.get('/api/sensor-data', async (req, res) => {
  const params = {
    Bucket: process.env.AWS_BUCKET_NAME,
    Key: 'sensor_data.json',
  };

  try {
    const data = await s3.getObject(params).promise();
    const jsonData = JSON.parse(data.Body.toString('utf-8'));

    if (Array.isArray(jsonData)) {
      res.json(jsonData);
    } else {
      res.status(400).json({ error: 'Malformed JSON file' });
    }
  } catch (err) {
    console.error("Error reading sensor_data.json:", err);
    res.status(500).json({ error: 'Error reading sensor_data.json from S3' });
  }
});

// Return only the latest entry
app.get('/api/current-sensor', async (req, res) => {
  const params = {
    Bucket: process.env.AWS_BUCKET_NAME,
    Key: 'sensor_data.json',
  };

  try {
    const data = await s3.getObject(params).promise();
    const jsonData = JSON.parse(data.Body.toString('utf-8'));

    if (Array.isArray(jsonData) && jsonData.length > 0) {
      res.json(jsonData[jsonData.length - 1]);
    } else {
      res.status(500).json({ error: 'File is empty or malformed' });
    }
  } catch (err) {
    console.error("Error reading current sensor data:", err);
    res.status(500).json({ error: 'Error reading sensor_data.json from S3' });
  }
});

// List of timestamps (dynamically extracted from sensor_data.json)
app.get('/api/history-timestamps', async (req, res) => {
  const params = {
    Bucket: process.env.AWS_BUCKET_NAME,
    Key: 'sensor_data.json',
  };

  try {
    const data = await s3.getObject(params).promise();
    const jsonData = JSON.parse(data.Body.toString('utf-8'));

    if (Array.isArray(jsonData)) {
      const timestamps = jsonData.map(entry => entry.timestamp).filter(Boolean);
      return res.json({ timestamps });
    }

    res.status(400).json({ error: 'Malformed JSON file' });
  } catch (err) {
    console.error("Error extracting timestamps:", err);
    res.status(500).json({ error: 'Error reading sensor_data.json from S3' });
  }
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});