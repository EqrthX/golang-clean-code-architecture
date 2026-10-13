import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiUrl, authenticatedFetch, clearTokens } from '../api'

type UserProfile = {
  id: number
  name: string
  email: string
}

export const ProfilePage = () => {
  const navigate = useNavigate()
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  useEffect(() => {
    const accessToken = localStorage.getItem('access_token')

    if (!accessToken) {
      navigate('/login', { replace: true })
      return
    }

    const controller = new AbortController()

    async function fetchProfile() {
      try {
        const response = await authenticatedFetch('/profile', {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}` },
          signal: controller.signal,
        })

        if (controller.signal.aborted) return

        if (response.status === 401) {
          clearTokens()
          navigate('/login', { replace: true })
          return
        }

        if (!response.ok) {
          setError('โหลดข้อมูลผู้ใช้ไม่สำเร็จ กรุณาลองใหม่')
          return
        }

        const profile: UserProfile = await response.json()
        if (!controller.signal.aborted) setUser(profile)
      } catch {
        if (!controller.signal.aborted) {
          setError('โหลดข้อมูลไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่')
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    void fetchProfile()

    // ยกเลิก request เมื่อออกจากหน้า รวมถึงรอบ cleanup ของ StrictMode
    return () => controller.abort()
  }, [navigate])

  async function handleLogout() {
    if (isLoggingOut) return
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      clearTokens()
      navigate('/login', { replace: true })
      return
    }
    setIsLoggingOut(true)
    setError('')
    try {
      const response = await fetch(apiUrl('/logout'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!response.ok && response.status !== 401) {
        setError('ออกจากระบบไม่สำเร็จ กรุณาลองใหม่')
        return
      }
      clearTokens()
      navigate('/login', { replace: true })
    } catch {
      setError('ออกจากระบบไม่สำเร็จ กรุณาตรวจสอบการเชื่อมต่อแล้วลองใหม่')
    } finally {
      setIsLoggingOut(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card profile-card" aria-labelledby="profile-title">
        <header className="auth-heading">
          <h1 id="profile-title">My profile</h1>
          <p>ข้อมูลบัญชีของคุณ</p>
        </header>

        {isLoading && <p role="status">กำลังโหลดข้อมูลผู้ใช้...</p>}

        {error && (
          <div className="profile-error">
            <p className="auth-error" role="alert">{error}</p>
            <button type="button" className="auth-submit" onClick={() => window.location.reload()}>
              ลองใหม่
            </button>
          </div>
        )}

        {!isLoading && user && (
          <>
            <dl className="profile-details">
              <div><dt>ชื่อ</dt><dd>{user.name}</dd></div>
              <div><dt>อีเมล</dt><dd>{user.email}</dd></div>
            </dl>
            <button type="button" className="auth-submit profile-logout"
              disabled={isLoggingOut} onClick={handleLogout}>
              {isLoggingOut ? 'กำลังออกจากระบบ...' : 'ออกจากระบบ'}
            </button>
          </>
        )}

        <p className="auth-footer"><Link to="/login">กลับหน้า Login</Link></p>
      </section>
    </main>
  )
}
