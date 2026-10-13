import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { apiError, apiUrl } from '../api'

export default function RegisterPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isSubmitting) return
    setError('')
    setSuccess('')
    if (password !== confirmPassword) {
      setError('รหัสผ่านและรหัสผ่านยืนยันไม่ตรงกัน')
      return
    }
    setIsSubmitting(true)
    try {
      const response = await fetch(apiUrl('/register'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      })
      if (!response.ok) {
        setError(await apiError(response, 'สมัครสมาชิกไม่สำเร็จ กรุณาลองใหม่'))
        return
      }
      setName('')
      setEmail('')
      setPassword('')
      setConfirmPassword('')
      setSuccess('สมัครสมาชิกสำเร็จ เข้าสู่ระบบได้เลย')
    } catch {
      setError('สมัครสมาชิกไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <>
      <form className="auth-form" onSubmit={handleSubmit} aria-busy={isSubmitting}>
        <div className="auth-field">
          <label htmlFor="name">Name</label>
          <input
            type="text" id="name" name="name" autoComplete="name"
            placeholder="ชื่อของคุณ" maxLength={100}
            value={name} onChange={event => { setName(event.target.value); setError('') }}
            required
          />
        </div>

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
              autoComplete="new-password" placeholder="กรอกรหัสผ่าน" minLength={8}
              aria-describedby="password-help"
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
          <small id="password-help">ใช้รหัสผ่านอย่างน้อย 8 ตัวอักษร</small>
        </div>

        <div className="auth-field">
          <label htmlFor="confirmPassword">Confirm password</label>
          <input
            type={showPassword ? 'text' : 'password'} id="confirmPassword" name="confirmPassword"
            autoComplete="new-password" placeholder="กรอกรหัสผ่านอีกครั้ง" minLength={8}
            value={confirmPassword}
            onChange={event => { setConfirmPassword(event.target.value); setError('') }}
            aria-invalid={error.includes('ยืนยัน') || undefined}
            aria-describedby={error ? 'form-error' : undefined}
            required
          />
        </div>

        {error && <p id="form-error" className="auth-error" role="alert">{error}</p>}
        {success && <p className="auth-success" role="status">{success}</p>}
        <button type="submit" className="auth-submit" disabled={isSubmitting}>
          {isSubmitting ? 'กำลังสมัครสมาชิก...' : 'Create account'} <span aria-hidden="true">→</span>
        </button>
      </form>

      <p className="auth-footer">มีบัญชีอยู่แล้ว? <Link to="/login">เข้าสู่ระบบ</Link></p>
    </>
  )
}
