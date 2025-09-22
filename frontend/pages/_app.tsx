import type { AppProps } from 'next/app'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from '../hooks/useAuth'
import 'bootstrap/dist/css/bootstrap.min.css'
import '../styles/globals.css'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <Component {...pageProps} />
      <Toaster 
        position="bottom-left" 
        toastOptions={{
          duration: 5000, // 5 seconds
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 5000,
            style: {
              background: '#4caf50',
              color: '#fff',
            },
          },
          error: {
            duration: 5000,
            style: {
              background: '#f44336',
              color: '#fff',
            },
          },
        }}
      />
    </AuthProvider>
  )
}