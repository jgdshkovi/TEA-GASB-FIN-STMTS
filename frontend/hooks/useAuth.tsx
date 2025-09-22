import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/router'
import { login as apiLogin, getCurrentUser, logout as apiLogout, User } from '../services/api'

interface AuthContextType {
  isAuthenticated: boolean
  user: User | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated on mount
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      console.log('Auth check - token exists:', !!token)
      if (token) {
        try {
          const userData = await getCurrentUser()
          console.log('Auth check - user data:', userData)
          setUser(userData)
          setIsAuthenticated(true)
        } catch (error) {
          console.log('Auth check - token invalid, clearing:', error)
          // Token is invalid, clear it
          localStorage.removeItem('access_token')
          localStorage.removeItem('isAuthenticated')
        }
      }
      console.log('Auth check - setting loading to false')
      setLoading(false)
    }

    checkAuth()
  }, [])

  const login = async (username: string, password: string) => {
    try {
      const response = await apiLogin({ username, password })
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem('isAuthenticated', 'true')
      
      // Get user data
      const userData = await getCurrentUser()
      setUser(userData)
      setIsAuthenticated(true)
      
      router.push('/')
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  const logout = () => {
    apiLogout()
    setUser(null)
    setIsAuthenticated(false)
    router.push('/login')
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
