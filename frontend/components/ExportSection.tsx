import { useState } from 'react'
import { Card, Button, Row, Col, Alert } from 'react-bootstrap'
import toast from 'react-hot-toast'
import { exportAuditTrail, downloadFile } from '../services/api'

export default function ExportSection() {
  const [exportingAudit, setExportingAudit] = useState(false)

  const handleExportAuditTrail = async () => {
    setExportingAudit(true)
    try {
      const blob = await exportAuditTrail()
      const filename = `audit_trail_${new Date().toISOString().split('T')[0]}.csv`
      downloadFile(blob, filename)
      toast.success('Audit trail downloaded successfully!')
    } catch (error) {
      toast.error('Error exporting audit trail')
      console.error('Error exporting audit trail:', error)
    } finally {
      setExportingAudit(false)
    }
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="mb-0">
          📥 Export
        </h2>
      </div>

      <Alert variant="info" className="mb-4">
        ✅ Export your audit trail and access financial statement exports. 
        Excel and PDF exports for financial statements are available in the Financial Statements section after generating statements.
      </Alert>

      <Row>
        <Col lg={6} className="mb-4">
          <Card className="h-100">
            <Card.Body className="text-center">
              <div className="mb-3">
                <div style={{fontSize: '48px'}}>🔍</div>
              </div>
              <h5>Audit Trail</h5>
              <p className="text-muted">
                Download detailed CSV showing how each trial balance line maps to statement categories
              </p>
              <Button 
                variant="primary" 
                className="w-100"
                onClick={handleExportAuditTrail}
                disabled={exportingAudit}
              >
                📥
                {exportingAudit ? 'Exporting...' : 'Download CSV'}
              </Button>
            </Card.Body>
          </Card>
        </Col>

        <Col lg={6} className="mb-4">
          <Card className="h-100">
            <Card.Body className="text-center">
              <div className="mb-3">
                <div style={{fontSize: '48px'}}>📊</div>
              </div>
              <h5>Financial Statements Export</h5>
              <p className="text-muted">
                Excel and PDF export options are now available in the Financial Statements section after generating statements.
              </p>
              <Button 
                variant="outline-primary" 
                className="w-100"
                disabled
              >
                📄
                Available in Financial Statements
              </Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Card className="mt-4">
        <Card.Header>
          <h6 className="mb-0">Export Information</h6>
        </Card.Header>
        <Card.Body>
          <Row>
            <Col md={6}>
              <h6>Financial Statement Exports (Available in Financial Statements section):</h6>
              <ul className="mb-0">
                <li>Excel: Government-wide Statement of Net Position</li>
                <li>Excel: Government-wide Statement of Activities</li>
                <li>Excel: Governmental Funds Balance Sheet</li>
                <li>Excel: Governmental Funds Statement of Revenues and Expenditures</li>
                <li>PDF: Print-ready formatted reports</li>
              </ul>
            </Col>
            <Col md={6}>
              <h6>Audit Trail Includes:</h6>
              <ul className="mb-0">
                <li>Original trial balance line items</li>
                <li>Mapped TEA/GASB categories</li>
                <li>Statement line assignments</li>
                <li>Any adjustments or rollups applied</li>
                <li>Complete transformation history</li>
              </ul>
            </Col>
          </Row>
        </Card.Body>
      </Card>
    </div>
  )
}