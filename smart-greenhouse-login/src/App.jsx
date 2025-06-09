import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import Settings from './pages/Settings';
import PlantGrowthGallery from './pages/PlantGrowthGallery';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/history" element={<History/>} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/growth-gallery" element={<PlantGrowthGallery />} />

      </Routes>
    </Router>
  );
}

export default App;