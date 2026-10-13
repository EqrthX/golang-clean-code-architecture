import { NavLink, Outlet, useLocation } from 'react-router-dom'

export default function AuthLayout() {
  const isRegister = useLocation().pathname === '/register'
  
  return (
    <main className="auth-page">
      <div className="auth-card">
        <nav className="auth-mode-toggle" aria-label="เลือกหน้าบัญชี">
          <NavLink to="/login" className={({ isActive }) => isActive ? 'auth-mode-active' : ''}>
            Login
          </NavLink>
          <NavLink to="/register" className={({ isActive }) => isActive ? 'auth-mode-active' : ''}>
            Register
          </NavLink>
        </nav>

        <section aria-labelledby="auth-title">
          <header className="auth-heading">
            <div className="auth-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <rect x="5" y="10" width="14" height="11" rx="3" />
                <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                <path d="M12 14v3" />
              </svg>
            </div>
            <h1 id="auth-title">{isRegister ? 'Create your account' : 'Welcome back'}</h1>
            <p>{isRegister ? 'กรอกข้อมูลเพื่อสร้างบัญชีของคุณ' : 'เข้าสู่ระบบเพื่อเริ่มใช้งานบัญชีของคุณ'}</p>
          </header>

          <Outlet />
        </section>
      </div>
    </main>
  )
}
