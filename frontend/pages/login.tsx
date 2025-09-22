import { useState } from 'react'
import Head from 'next/head'
import { Container, Row, Col, Card, Form, Button, Alert, Nav } from 'react-bootstrap'
import { useAuth } from '../hooks/useAuth'
import { useRouter } from 'next/router'
import Link from 'next/link'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      await login(username, password)
      // Navigation is handled in the login function
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Head>
        <title>Login - TEA Financial Statement Generator</title>
        <meta name="description" content="Login to access the TEA Financial Statement Generator" />
      </Head>

      <div 
        style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center'
        }}
      >
        <Container>
          <Row className="justify-content-center">
            <Col md={6} lg={4}>
              <Card className="shadow-lg border-0" style={{ borderRadius: '15px' }}>
                <Card.Body className="p-4">
                  <div className="text-center mb-4">
                    <div 
                      className="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                      style={{ width: '60px', height: '60px' }}
                    >
                      🔐
                    </div>
                    <h3 className="mb-1">TEA Financial Generator</h3>
                    <p className="text-muted mb-0">Secure Login</p>
                  </div>
                  
                  {error && (
                    <Alert variant="danger" className="mb-3">
                      ⚠️ {error}
                    </Alert>
                  )}
                  
                  <Form onSubmit={handleSubmit}>
                    <Form.Group className="mb-3">
                      <Form.Label>Email</Form.Label>
                      <Form.Control
                        type="email"
                        placeholder="Enter your email"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                        disabled={loading}
                      />
                    </Form.Group>
                    
                    <Form.Group className="mb-4">
                      <Form.Label>Password</Form.Label>
                      <Form.Control
                        type="password"
                        placeholder="Enter password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={loading}
                      />
                    </Form.Group>
                    
                    <Button 
                      type="submit" 
                      className="w-100 mb-3"
                      disabled={loading}
                      style={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        borderRadius: '8px',
                        padding: '12px'
                      }}
                    >
                      {loading ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                          Signing in...
                        </>
                      ) : (
                        <>
                          Sign In
                        </>
                      )}
                    </Button>
                  </Form>
                  
                  <div className="text-center">
                    <p className="mb-0">
                      Don't have an account?{' '}
                      <Link href="/register" passHref>
                        <Nav.Link as="span" className="d-inline p-0 text-primary">
                          Sign up here
                        </Nav.Link>
                      </Link>
                    </p>
                  </div>
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </Container>
      </div>
    </>
  )
}
