import { useState, useEffect } from 'react'
import { Card, Alert, Button, Table, Row, Col, Spinner } from 'react-bootstrap'
import { FiSearch, FiDownload, FiCheckCircle, FiAlertTriangle } from 'react-icons/fi'
import toast from 'react-hot-toast'
import { getAuditTrail, exportAuditTrail, downloadFile, AuditTrailItem } from '../services/api'

export default function AuditSection() {
  const [auditData, setAuditData] = useState<AuditTrailItem[]>([])
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    loadAuditData()
  }, [])

  const loadAuditData = async () => {
    setLoading(true)
    try {
      const response = await getAuditTrail()
      if (response.success && response.audit_data) {
        setAuditData(response.audit_data)
      }
    } catch (error) {
      toast.error('Error loading audit data')
      console.error('Error loading audit data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExportAuditTrail = async () => {
    setExporting(true)
    try {
      const blob = await exportAuditTrail()
      const filename = `audit_trail_${new Date().toISOString().split('T')[0]}.csv`
      downloadFile(blob, filename)
      toast.success('Audit trail downloaded successfully!')
    } catch (error) {
      toast.error('Error exporting audit trail')
      console.error('Error exporting audit trail:', error)
    } finally {
      setExporting(false)
    }
  }

  const getValidationStatus = () => {
    if (!auditData || auditData.length === 0) return { 
      status: 'warning', 
      message: 'No data available',
      totalCount: 0,
      mappedCount: 0,
      unmappedCount: 0,
      unknownTotal: 0,
      unknownCount: 0
    }
    
    // Count mapped vs unmapped accounts
    const unmappedCount = auditData.filter(item => item.unmapped_accounts).length
    const totalCount = auditData.length
    const mappedCount = totalCount - unmappedCount
    
    // Calculate totals for balance validation
    let totalDebits = 0
    let totalCredits = 0
    let unknownDebits = 0
    let unknownCredits = 0
    let unknownCount = 0
    
    auditData.forEach(item => {
      const amount = Math.abs(item.current_year_actual)
      const teaCategory = item.tea_category.toLowerCase()
      const gasbCategory = item.gasb_category.toLowerCase()
      
      // Only count truly unmapped accounts as unknown
      if (item.unmapped_accounts) {
        unknownCount++
        if (item.current_year_actual > 0) {
          totalDebits += amount
          unknownDebits += amount
        } else {
          totalCredits += amount
          unknownCredits += amount
        }
      } else {
        // For mapped accounts, determine if this account type is normally a debit or credit account
        // Check TEA category first, then GASB category as fallback
        if (isDebitAccount(teaCategory) || isDebitAccount(gasbCategory)) {
          totalDebits += amount
        } else if (isCreditAccount(teaCategory) || isCreditAccount(gasbCategory)) {
          totalCredits += amount
        } else {
          // If we can't determine debit/credit for a mapped account, 
          // treat it as debit if positive, credit if negative
          if (item.current_year_actual > 0) {
            totalDebits += amount
          } else {
            totalCredits += amount
          }
        }
      }
    })
    
    const difference = Math.abs(totalDebits - totalCredits)
    const totalUnknown = unknownDebits + unknownCredits
    
    let message = ''
    if (unmappedCount === 0) {
      message = `All ${totalCount} accounts are properly mapped`
    } else if (unmappedCount < totalCount * 0.1) {
      message = `${mappedCount}/${totalCount} accounts mapped (${unmappedCount} unmapped)`
    } else {
      message = `${mappedCount}/${totalCount} accounts mapped (${unmappedCount} unmapped)`
    }
    
    if (totalUnknown > 0) {
      message += ` | Unknown: $${totalUnknown.toLocaleString()} (${unknownCount} accounts)`
    }
    
    let status = 'success'
    if (unmappedCount > 0) {
      status = unmappedCount < totalCount * 0.1 ? 'warning' : 'danger'
    }
    // if (difference > 1) {
    //   status = 'danger'
    // }
    
    return { 
      status, 
      message,
      unknownTotal: totalUnknown,
      unknownCount,
      unmappedCount,
      mappedCount,
      totalCount
    }
  }

  const isDebitAccount = (category: string) => {
    // Assets, Expenses, and Expenditures are debit accounts
    return category.includes('asset') || 
           category.includes('expense') || 
           category.includes('expenditure') ||
           category.includes('cash') ||
           category.includes('receivable') ||
           category.includes('inventory') ||
           category.includes('capital_asset') ||
           category.includes('current_asset') ||
           category.includes('deferred_outflow') ||
           category.includes('program_expense') ||
           category.includes('general_expense') ||
           category === 'assets' ||
           category === 'expenditures/expenses' ||
           category === 'other_uses' ||
           category === 'program_expenses' ||
           category === 'general_expenses'
  }

  const isCreditAccount = (category: string) => {
    // Liabilities, Equity, Revenues, and Fund Balances are credit accounts
    return category.includes('liability') || 
           category.includes('equity') || 
           category.includes('revenue') ||
           category.includes('payable') ||
           category.includes('debt') ||
           category.includes('fund_balance') ||
           category.includes('net_position') ||
           category.includes('current_liability') ||
           category.includes('general_revenue') ||
           category.includes('restricted_net_position') ||
           category.includes('other resources') ||
           category.includes('non-operating') ||
           category === 'liabilities' ||
           category === 'revenues' ||
           category === 'other resources/non-operating revenues' ||
           category === 'fund balances/net position' ||
           category === 'other_resources' ||
           category === 'program_revenues' ||
           category === 'general_revenues'
  }

  const validation = getValidationStatus()

  if (loading) {
    return (
      <div className="text-center py-5">
        <Spinner animation="border" role="status" className="text-primary">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-3">Loading audit trail...</p>
      </div>
    )
  }

  const getStatementTypeBadgeColor = (statementType: string) => {
    switch (statementType) {
      case 'Net Position': return 'bg-primary'
      case 'Activities': return 'bg-success'
      case 'Balance Sheet': return 'bg-info'
      case 'Revenues & Expenditures': return 'bg-warning'
      default: return 'bg-secondary'
    }
  }

  const getMappingMethodBadgeColor = (method: string) => {
    switch (method) {
      case 'auto_mapped': return 'bg-success'
      case 'manual_mapped': return 'bg-primary'
      case 'unmapped': return 'bg-warning'
      default: return 'bg-secondary'
    }
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="mb-0">
          {/* <FiSearch className="me-2" /> */}
          🔍
          Audit Trail
        </h2>
      </div>

      <Alert variant="info" className="mb-4">
        <FiSearch className="me-2" />
        This shows how each trial balance line maps to statement categories, 
        including any adjustments or rollups applied. Use this for validation and compliance purposes.
      </Alert>

      <Row className="mb-4">
        <Col md={6}>
          <Card>
            <Card.Body>
              <h6 className="mb-3">Validation Status</h6>
              <Alert variant={validation.status}>
                <FiCheckCircle className="me-2" />
                {validation.message}
              </Alert>
            </Card.Body>
          </Card>
        </Col>
        {/* <Col md={3}>
          <Card>
            <Card.Body>
              <h6 className="mb-3">Summary</h6>
              <p className="mb-1"><strong>Total Records:</strong> {validation?.totalCount?.toLocaleString() || '0'}</p>
              <p className="mb-1"><strong>Mapped:</strong> {validation?.mappedCount?.toLocaleString() || '0'}</p>
              <p className="mb-1"><strong>Unmapped:</strong> {validation?.unmappedCount?.toLocaleString() || '0'}</p>
              <p className="mb-1"><strong>Statement Types:</strong> {new Set(auditData.map(item => item.statement_type)).size}</p>
              {validation?.unknownTotal > 0 && (
                <p className="mb-0">
                  <strong className="text-warning">Unknown Balances:</strong> 
                  <br />
                  <span className="text-warning">${validation.unknownTotal.toLocaleString()} ({validation.unknownCount} accounts)</span>
                </p>
              )}
            </Card.Body>
          </Card>
        </Col> */}
        <Col md={6}>
          <Card>
            <Card.Body className="text-center">
              <div className="mb-3">
                <Button 
                  variant="primary" 
                  size="sm"
                  onClick={handleExportAuditTrail}
                  disabled={exporting || auditData.length === 0}
                >
                  <FiDownload className="me-2" />
                  {exporting ? 'Exporting...' : 'Download CSV'}
                </Button>
              </div>
              {/* <h6>Download CSV</h6> */}
              <p className="text-muted small">
                Download detailed CSV showing how each trial balance line maps to statement categories
              </p>
              
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Card>
        <Card.Header>
          <h6 className="mb-0">Detailed Audit Trail</h6>
        </Card.Header>
        <Card.Body>
          {auditData.length > 0 ? (
            <div className="table-responsive">
              <Table striped hover>
                <thead>
                  <tr>
                    <th>Account Code</th>
                    <th className="text-end">Current Year</th>
                    <th className="text-end">Budget</th>
                    <th className="text-end">Prior Year</th>
                    <th>Fund</th>
                    <th>Function</th>
                    <th>Object</th>
                    <th>Statement Type</th>
                    <th>Statement Line</th>
                    <th>Mapping Method</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {auditData.slice(0, 100).map((item, index) => (
                    <tr key={index}>
                      <td>
                        <code>{item.account_code}</code>
                      </td>
                      <td className="text-end">
                        ${item.current_year_actual.toLocaleString()}
                      </td>
                      <td className="text-end">
                        ${item.budget.toLocaleString()}
                      </td>
                      <td className="text-end">
                        ${item.prior_year_actual.toLocaleString()}
                      </td>
                      <td>
                        <small>{item.fund_code}</small>
                      </td>
                      <td>
                        <small>{item.function_code}</small>
                      </td>
                      <td>
                        <small>{item.object_code}</small>
                      </td>
                      <td>
                        <span className={`badge ${getStatementTypeBadgeColor(item.statement_type)}`}>
                          {item.statement_type}
                        </span>
                      </td>
                      <td>
                        <small>
                          {item.statement_line_code} - {item.statement_line_description}
                        </small>
                      </td>
                      <td>
                        <span className={`badge ${getMappingMethodBadgeColor(item.mapping_method)}`}>
                          {item.mapping_method}
                        </span>
                      </td>
                      <td>
                        {item.unmapped_accounts ? (
                          <span className="badge bg-warning">Unmapped</span>
                        ) : (
                          <span className="badge bg-success">Mapped</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              
              {auditData.length > 100 && (
                <div className="text-center mt-3">
                  <Alert variant="info">
                    Showing first 100 records. Download the full audit trail CSV to see all {auditData.length.toLocaleString()} records.
                  </Alert>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-5 text-muted">
              <FiAlertTriangle size={48} className="mb-3" />
              <h5>No Audit Data Available</h5>
              <p>Please upload a trial balance file to generate the audit trail.</p>
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  )
}
