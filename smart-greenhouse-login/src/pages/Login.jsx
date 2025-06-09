import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import logo from '../assets/logo.png';
import '/src/style/App.css'

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate(); // 👈 ajoute useNavigate()

  const handleSubmit = (e) => {
    e.preventDefault();

    // Verification simulation (replace with the API call )
    if (email === 'test@example.com' && password === '1234') {
      setError('');
      console.log('Login success!');
      navigate('/dashboard'); // 👈 redirection vers /dashboard
    } else {
      setError('Invalid email or password');
    }
  };

  return (
    <div className="mt-5">
      <h1 className="d-flex align-items-center justify-content-center mb-5"> SmartGreen House </h1>
      <div className="login_card container d-flex align-items-center justify-content-center card shadow p-4">
        <h2 className="text-center mb-4">Login</h2>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">Email address</label>
            <input
              type="email"
              className="form-control"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-control"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary w-100">Login</button>
        </form>

        <p className="text-center mt-3 mb-0">
          Don't have an account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}