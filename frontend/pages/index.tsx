import { useState, useEffect } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'
import { Nav, Button } from 'react-bootstrap'
import UploadSection from '../components/UploadSection'
import MappingSection from '../components/MappingSection'
import StatementsSection from '../components/StatementsSection'
// import ExportSection from '../components/ExportSection' // Commented out - functionality moved to Financial Statements and Audit Trail sections
import AuditSection from '../components/AuditSection'
import { useAuth } from '../hooks/useAuth'

export default function Home() {
  const [activeSection, setActiveSection] = useState('upload')
  const [mappingLoadTrigger, setMappingLoadTrigger] = useState(false)
  const { isAuthenticated, user, logout, loading } = useAuth()
  const router = useRouter()

  // All hooks must be called before any conditional returns
  useEffect(() => {
    console.log('Index page - loading:', loading, 'isAuthenticated:', isAuthenticated)
    if (!loading && !isAuthenticated) {
      console.log('Index page - redirecting to login')
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <div className="text-center">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p className="mt-3">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <div className="text-center">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Redirecting...</span>
          </div>
          <p className="mt-3">Redirecting to login...</p>
        </div>
      </div>
    )
  }

  const sections = [
    { id: 'upload', label: 'Upload Data', icon: '📤' },
    { id: 'mapping', label: 'Account Mapping', icon: '🗺️' },
    { id: 'statements', label: 'Financial Statements', icon: '📊' },
    // { id: 'exports', label: 'Export', icon: '📥' }, // Commented out - functionality moved to Financial Statements and Audit Trail sections
    { id: 'audit', label: 'Audit Trail', icon: '🔍' },
  ]

  const handleNavigateToMapping = () => {
    setMappingLoadTrigger(true)
    setActiveSection('mapping')
  }

  const handleMappingLoadComplete = () => {
    setMappingLoadTrigger(false)
  }

  const renderSection = () => {
    switch (activeSection) {
      case 'upload':
        return <UploadSection onNavigateToMapping={handleNavigateToMapping} />
      case 'mapping':
        return <MappingSection 
          loadTrigger={mappingLoadTrigger} 
          onLoadComplete={handleMappingLoadComplete} 
        />
      case 'statements':
        return <StatementsSection />
      // case 'exports':
      //   return <ExportSection /> // Commented out - functionality moved to Financial Statements and Audit Trail sections
      case 'audit':
        return <AuditSection />
      default:
        return <UploadSection onNavigateToMapping={handleNavigateToMapping} />
    }
  }

  return (
    <>
      <Head>
        <title>TEA Financial Statement Generator</title>
        <meta name="description" content="Process Texas school district trial balances and generate TEA/GASB financial statements" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div>
        {/* Fixed Sidebar */}
        <div className="sidebar p-3">
          <div className="text-center mb-4">
            <h5 className="text-primary mb-0">TEA Financial Generator</h5>
            <small className="text-muted">v1.0.0</small>
            {user && (
              <div className="mt-3 p-2 bg-light rounded">
                <small className="text-muted d-block">Welcome,</small>
                <strong className="text-primary">
                  {user.first_name && user.last_name 
                    ? `${user.first_name} ${user.last_name}`
                    : user.email
                  }
                </strong>
                {user.organization && (
                  <small className="text-muted d-block">{user.organization}</small>
                )}
              </div>
            )}
          </div>
          
          <Nav className="flex-column">
            {sections.map(({ id, label, icon }) => (
              <Nav.Link
                key={id}
                className={`nav-link ${activeSection === id ? 'active' : ''}`}
                onClick={() => setActiveSection(id)}
              >
                <span className="me-2">{icon}</span>
                {label}
              </Nav.Link>
            ))}
          </Nav>
          
          <hr className="my-4" />
          
          <div className="text-center">
            <Button 
              variant="outline-danger"
              size="sm"
              onClick={logout}
            >
              🚪 Logout
            </Button>
          </div>
        </div>

        {/* Main Content */}
        <div className="main-content">
          {renderSection()}
        </div>
      </div>
    </>
  )
}
