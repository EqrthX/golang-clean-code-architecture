import { Link, Navigate, Route, Routes } from 'react-router-dom'
import AuthLayout from './components/AuthLayout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import { ProfilePage } from './pages/ProfilePage'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="*" element={
        <main className="auth-page">
          <div className="auth-card">
            <h1>ไม่พบหน้านี้</h1>
            <p className="auth-footer"><Link to="/login">กลับหน้า Login</Link></p>
          </div>
        </main>
      } />
    </Routes>
  )
}
