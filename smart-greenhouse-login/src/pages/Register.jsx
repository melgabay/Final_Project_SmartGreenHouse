import React, { useState } from 'react';
import { Link } from 'react-router-dom';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords don't match");
      setSuccess('');
      return;
    }

    // Simulate successful registration
    setError('');
    setSuccess('Account created successfully!');
    console.log('Register:', { email, password });

    // Clear form (optional)
    setEmail('');
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <div className="mt-5">
      <h1 className="d-flex align-items-center justify-content-center"> SmartGreen House </h1>
      <div className="login_card container d-flex align-items-center justify-content-center card shadow p-4">
        <h2 className="text-center mb-4">Register</h2>

        {error && <div className="alert alert-danger">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

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
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="mb-3">
            <label className="form-label">Confirm Password</label>
            <input
              type="password"
              className="form-control"
              placeholder="Repeat password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary w-100">Register</button>
        </form>

        <p className="text-center mt-3 mb-0">
          Already have an account? <Link to="/">Login</Link>
        </p>
      </div>
    </div>
  );
}