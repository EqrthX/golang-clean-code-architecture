import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiError, apiUrl, saveTokens } from '../api'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) return
    setError('')
    setIsSubmitting(true)
    try {
      const response = await fetch(apiUrl('/login'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!response.ok) {
        setError(await apiError(response, 'เข้าสู่ระบบไม่สำเร็จ กรุณาลองใหม่'))
        return
      }
      saveTokens(await response.json())
      setPassword('')
      navigate('/profile', { replace: true })
    } catch {
      setError('เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <form className="auth-form" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <div className="auth-field">
          <label htmlFor="email">Email address</label>
          <input
            type="email" id="email" name="email" autoComplete="email"
            placeholder="you@example.com" autoCapitalize="none" spellCheck={false}
            value={email} onChange={event => { setEmail(event.target.value); setError('') }}
            required
          />
        </div>

        <div className="auth-field">
          <label htmlFor="password">Password</label>
          <div className="auth-password">
            <input
              type={showPassword ? 'text' : 'password'} id="password" name="password"
              autoComplete="current-password" placeholder="กรอกรหัสผ่าน" minLength={1}
              value={password} onChange={event => { setPassword(event.target.value); setError('') }}
              required
            />
            <button
              type="button" className="auth-password-toggle"
              aria-label={showPassword ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'}
              onClick={() => setShowPassword(current => !current)}
            >
              {showPassword ? 'ซ่อน' : 'แสดง'}
            </button>
          </div>
        </div>

        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="auth-submit" disabled={isSubmitting}>
          {isSubmitting ? 'กำลังเข้าสู่ระบบ...' : 'Login'} <span aria-hidden="true">→</span>
        </button>
      </form>

      <p className="auth-footer">ยังไม่มีบัญชี? <Link to="/register">สมัครสมาชิก</Link></p>
    </>
  )
}
