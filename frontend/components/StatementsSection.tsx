import { useState, useEffect } from 'react'
import { Card, Alert, Button, Table, Row, Col, Spinner } from 'react-bootstrap'
import toast from 'react-hot-toast'
import { getMapping, generateStatements, exportToExcel, downloadFile } from '../services/api'

interface FinancialStatements {
  government_wide_net_position: any
  government_wide_activities: any
  governmental_funds_balance: any
  governmental_funds_revenues_expenditures: any
}

export default function StatementsSection() {
  const [statements, setStatements] = useState<FinancialStatements | null>(null)
  const [generating, setGenerating] = useState(false)
  const [mapping, setMapping] = useState<any>(null)
  const [exportingExcel, setExportingExcel] = useState(false)

  useEffect(() => {
    loadMapping()
  }, [])

  // Auto-generate statements when mapping is loaded
  useEffect(() => {
    if (mapping && Object.keys(mapping).length > 0) {
      handleGenerateStatements()
    }
  }, [mapping])

  const loadMapping = async () => {
    try {
      const mappingData = await getMapping()
      setMapping(mappingData)
    } catch (error) {
      console.error('Error loading mapping:', error)
    }
  }

  const handleGenerateStatements = async () => {
    if (!mapping || Object.keys(mapping).length === 0) {
      toast.error('Please configure account mapping first')
      return
    }

    setGenerating(true)
    try {
      const response = await generateStatements(mapping)
      if (response.success) {
        setStatements(response.statements)
        toast.success('Financial statements generated successfully!')
      } else {
        toast.error('Error generating statements')
      }
    } catch (error) {
      toast.error('Error generating statements')
      console.error('Error generating statements:', error)
    } finally {
      setGenerating(false)
    }
  }

  const handleExportExcel = async () => {
    setExportingExcel(true)
    try {
      const blob = await exportToExcel()
      const filename = `financial_statements_${new Date().toISOString().split('T')[0]}.xlsx`
      downloadFile(blob, filename)
      toast.success('Excel file downloaded successfully!')
    } catch (error) {
      toast.error('Error exporting to Excel')
      console.error('Error exporting to Excel:', error)
    } finally {
      setExportingExcel(false)
    }
  }


  const handlePrintPDF = () => {
    // Simple print functionality - in production, implement proper PDF generation
    window.print()
    toast.success('Print dialog opened. Use "Save as PDF" to create a PDF file.')
  }

  const renderStatementTable = (title: string, data: any) => {
    if (!data || Object.keys(data).length === 0) {
      return (
        <div className="text-center py-4 text-muted">
          ⚠️ No data available
        </div>
      )
    }

    return (
      <Table striped hover className="mb-0">
        <thead>
          <tr>
            <th>Category</th>
            <th className="text-end">Amount</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(data).map(([key, value]: [string, any]) => (
            <tr key={key}>
              <td>
                <strong>{key.replace(/_/g, ' ').toUpperCase()}</strong>
              </td>
              <td className="text-end">
                {typeof value === 'number' ? 
                  `$${value.toLocaleString()}` : 
                  (typeof value === 'object' && value !== null ? 
                    `$${Object.values(value).reduce((sum: number, val: any) => 
                      sum + (typeof val === 'number' ? val : 0), 0).toLocaleString()}` : 
                    'XX'
                  )
                }
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    )
  }

  const renderNetPositionStatement = (data: any) => {
    if (!data || !data.title) {
      return (
        <div className="text-center py-4 text-muted">
          ⚠️ No data available
        </div>
      )
    }

    const formatAmount = (amount: number) => {
      if (amount === 0) return '-'
      return `$${amount.toLocaleString()}`
    }

    const renderLineItem = (item: any, indent: boolean = false) => (
      <tr key={item.code}>
        <td className={indent ? 'ps-4' : ''}>
          {item.code}
        </td>
        <td className={indent ? 'ps-4' : ''}>
          {item.description}
        </td>
        <td className="text-end">
          {formatAmount(item.amount)}
        </td>
      </tr>
    )

    const renderSection = (title: string, items: any, indent: boolean = false) => (
      <>
        <tr className="table-secondary">
          <td colSpan={3} className="fw-bold">
            {title}:
          </td>
        </tr>
        {Object.entries(items).map(([key, value]: [string, any]) => {
          if (key === 'total_assets' || key === 'total_deferred_outflows' || 
              key === 'total_liabilities' || key === 'total_deferred_inflows' || 
              key === 'total_net_position') {
            return (
              <tr key={value.code} className="table-primary fw-bold">
                <td>
                  {value.code}
                </td>
                <td>
                  {value.description}
                </td>
                <td className="text-end">
                  {formatAmount(value.amount)}
                </td>
              </tr>
            )
          } else if (typeof value === 'object' && value.code && value.description !== undefined) {
            return renderLineItem(value, indent)
          } else if (typeof value === 'object' && key === 'capital_assets') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Capital Assets:</td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderLineItem(subValue, true)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'noncurrent_liabilities') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Noncurrent Liabilities:</td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderLineItem(subValue, true)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'restricted') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Restricted For:</td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderLineItem(subValue, true)
                )}
              </>
            )
          }
          return null
        })}
      </>
    )

    return (
      <div>
        <div className="text-center mb-3">
          <h4 className="mb-1">{data.title}</h4>
          <div className="text-muted small">{data.subtitle}</div>
        </div>
        
        <Table striped hover className="mb-0">
          <thead>
            <tr>
              <th>Data Control Codes</th>
              <th>Description</th>
              <th className="text-end">Governmental Activities</th>
            </tr>
          </thead>
          <tbody>
            {renderSection('ASSETS', data.assets)}
            {renderSection('DEFERRED OUTFLOWS OF RESOURCES', data.deferred_outflows)}
            {renderSection('LIABILITIES', data.liabilities)}
            {renderSection('DEFERRED INFLOWS OF RESOURCES', data.deferred_inflows)}
            {renderSection('NET POSITION', data.net_position)}
          </tbody>
        </Table>

        {/* Balance Validation */}
        {data.balance_validation && (
          <div className="mt-3 p-3 bg-light rounded">
            <h6>Balance Validation:</h6>
            <div className="row">
              <div className="col-md-6">
                <strong>Left Side (Assets + Deferred Outflows):</strong><br/>
                {formatAmount(data.balance_validation.left_side)}
              </div>
              <div className="col-md-6">
                <strong>Right Side (Liabilities + Deferred Inflows + Net Position):</strong><br/>
                {formatAmount(data.balance_validation.right_side)}
              </div>
            </div>
            <div className="mt-2">
              <span className={`badge ${data.balance_validation.balanced ? 'bg-success' : 'bg-danger'}`}>
                {data.balance_validation.balanced ? '✅ BALANCED' : '❌ OUT OF BALANCE'}
              </span>
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderActivitiesStatement = (data: any) => {
    if (!data || !data.title) {
      return (
        <div className="text-center py-4 text-muted">
          ⚠️ No data available
        </div>
      )
    }

    const formatAmount = (amount: number) => {
      if (amount === 0) return '--'
      return `$${amount.toLocaleString()}`
    }

    const formatNetAmount = (amount: number) => {
      if (amount === 0) return '--'
      if (amount < 0) return `(${Math.abs(amount).toLocaleString()})`
      return `$${amount.toLocaleString()}`
    }

    const renderProgramRow = (program: any) => (
      <tr key={program.code}>
        <td>{program.code}</td>
        <td>{program.description}</td>
        <td className="text-end">{formatAmount(program.expenses)}</td>
        <td className="text-end">{formatAmount(program.charges_for_services)}</td>
        <td className="text-end">{formatAmount(program.operating_grants)}</td>
        <td className="text-end">{formatNetAmount(program.net_expense_revenue)}</td>
      </tr>
    )

    const renderRevenueRow = (revenue: any) => (
      <tr key={revenue.code || revenue.description}>
        <td>{revenue.code}</td>
        <td>{revenue.description}</td>
        <td className="text-end">{formatAmount(revenue.amount)}</td>
      </tr>
    )

    const renderNetPositionRow = (item: any) => (
      <tr key={item.code}>
        <td>{item.code}</td>
        <td>{item.description}</td>
        <td className="text-end">{formatAmount(item.amount)}</td>
      </tr>
    )

    return (
      <div>
        <div className="text-center mb-3">
          <h4 className="mb-1">{data.title}</h4>
        </div>
        
        {/* Governmental Activities Section */}
        <div className="mb-4">
          <h6 className="mb-3">Governmental Activities (Program Expenses and Revenues)</h6>
          <Table striped hover className="mb-0">
            <thead>
              <tr>
                <th rowSpan={2} className="align-middle">Data Control Codes</th>
                <th rowSpan={2} className="align-middle">Functions/Programs</th>
                <th rowSpan={2} className="text-end align-middle">Expenses</th>
                <th colSpan={2} className="text-center">Program Revenues</th>
                <th colSpan={1} className="text-center">Net (Expense) Revenue and Changes in Net Position</th>
              </tr>
              <tr>
                <th className="text-end">Charges for Services</th>
                <th className="text-end">Operating Grants and Contributions</th>
                <th className="text-end">Governmental Activities</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.governmental_activities).map(([key, program]: [string, any]) => {
                if (key === 'total_governmental' || key === 'total_primary') {
                  return (
                    <tr key={program.code} className="table-primary fw-bold">
                      <td>{program.code}</td>
                      <td>{program.description}</td>
                      <td className="text-end">{formatAmount(program.expenses)}</td>
                      <td className="text-end">{formatAmount(program.charges_for_services)}</td>
                      <td className="text-end">{formatAmount(program.operating_grants)}</td>
                      <td className="text-end">{formatNetAmount(program.net_expense_revenue)}</td>
                    </tr>
                  )
                }
                return renderProgramRow(program)
              })}
            </tbody>
          </Table>
        </div>

        {/* General Revenues Section */}
        <div className="mb-4">
          <h6 className="mb-3">General Revenues:</h6>
          <Table striped hover className="mb-0">
            <thead>
              <tr>
                <th>Data Control Codes</th>
                <th>Description</th>
                <th className="text-end">Amount</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.general_revenues).map(([key, revenue]: [string, any]) => {
                if (key === 'total_general_revenues') {
                  return (
                    <tr key={revenue.code} className="table-primary fw-bold">
                      <td>{revenue.code}</td>
                      <td>{revenue.description}</td>
                      <td className="text-end">{formatAmount(revenue.amount)}</td>
                    </tr>
                  )
                }
                return renderRevenueRow(revenue)
              })}
            </tbody>
          </Table>
        </div>

        {/* Net Position Section */}
        <div>
          <Table striped hover className="mb-0">
            <tbody>
              {Object.entries(data.net_position).map(([key, item]: [string, any]) => {
                if (key === 'net_position_ending') {
                  return (
                    <tr key={item.code} className="table-primary fw-bold">
                      <td>{item.code}</td>
                      <td>{item.description}</td>
                      <td className="text-end">{formatAmount(item.amount)}</td>
                    </tr>
                  )
                }
                return renderNetPositionRow(item)
              })}
            </tbody>
          </Table>
        </div>
      </div>
    )
  }

  const renderBalanceSheetStatement = (data: any) => {
    if (!data || !data.title) {
      return (
        <div className="text-center py-4 text-muted">
          ⚠️ No data available
        </div>
      )
    }

    const formatAmount = (amount: number) => {
      if (amount === 0) return '--'
      return `$${amount.toLocaleString()}`
    }

    const renderFundRow = (item: any) => (
      <tr key={item.code}>
        <td>{item.code}</td>
        <td>{item.description}</td>
        <td className="text-end">{formatAmount(item.general_fund)}</td>
        <td className="text-end">{formatAmount(item.non_major_funds)}</td>
      </tr>
    )

    const renderSection = (title: string, items: any, indent: boolean = false) => (
      <>
        <tr className="table-secondary">
          <td colSpan={4} className="fw-bold">
            {title}:
          </td>
        </tr>
        {Object.entries(items).map(([key, value]: [string, any]) => {
          if (key === 'total_assets' || key === 'total_liabilities' || 
              key === 'total_deferred_inflows' || key === 'total_fund_balances' ||
              key === 'total_liabilities_deferred_fund_balances') {
            return (
              <tr key={value.code} className="table-primary fw-bold">
                <td>{value.code}</td>
                <td>{value.description}</td>
                <td className="text-end">{formatAmount(value.general_fund)}</td>
                <td className="text-end">{formatAmount(value.non_major_funds)}</td>
              </tr>
            )
          } else if (typeof value === 'object' && value.code && value.description !== undefined) {
            return renderFundRow(value)
          } else if (typeof value === 'object' && key === 'current_liabilities') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Current Liabilities:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'nonspendable') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Nonspendable Fund Balances:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'restricted') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Restricted Fund Balances:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'committed') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Committed Fund Balances:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          } else if (typeof value === 'object' && key === 'assigned') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Assigned Fund Balances:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          }
          return null
        })}
      </>
    )

    return (
      <div>
        <div className="text-center mb-3">
          <h4 className="mb-1">{data.title}</h4>
        </div>
        
        <Table striped hover className="mb-0">
          <thead>
            <tr>
              <th>Data Control Codes</th>
              <th>Description</th>
              <th className="text-end">{data.funds.general_fund}</th>
              <th className="text-end">{data.funds.non_major_funds}</th>
            </tr>
          </thead>
          <tbody>
            {renderSection('ASSETS', data.assets)}
            {renderSection('LIABILITIES', data.liabilities)}
            {renderSection('DEFERRED INFLOWS OF RESOURCES', data.deferred_inflows)}
            {renderSection('FUND BALANCES', data.fund_balances)}
            <tr className="table-primary fw-bold">
              <td>{data.total_liabilities_deferred_fund_balances.code}</td>
              <td>{data.total_liabilities_deferred_fund_balances.description}</td>
              <td className="text-end">{formatAmount(data.total_liabilities_deferred_fund_balances.general_fund)}</td>
              <td className="text-end">{formatAmount(data.total_liabilities_deferred_fund_balances.non_major_funds)}</td>
            </tr>
          </tbody>
        </Table>
      </div>
    )
  }

  const renderRevenuesExpendituresStatement = (data: any) => {
    if (!data || !data.title) {
      return (
        <div className="text-center py-4 text-muted">
          ⚠️ No data available
        </div>
      )
    }

    const formatAmount = (amount: number) => {
      if (amount === 0) return '--'
      return `$${amount.toLocaleString()}`
    }

    const formatNetAmount = (amount: number) => {
      if (amount === 0) return '--'
      if (amount < 0) return `(${Math.abs(amount).toLocaleString()})`
      return `$${amount.toLocaleString()}`
    }

    const renderFundRow = (item: any) => (
      <tr key={item.code}>
        <td>{item.code}</td>
        <td>{item.description}</td>
        <td className="text-end">{formatAmount(item.general_fund)}</td>
        <td className="text-end">{formatAmount(item.non_major_funds)}</td>
      </tr>
    )

    const renderNetRow = (item: any) => (
      <tr key={item.code}>
        <td>{item.code}</td>
        <td>{item.description}</td>
        <td className="text-end">{formatNetAmount(item.general_fund)}</td>
        <td className="text-end">{formatNetAmount(item.non_major_funds)}</td>
      </tr>
    )

    const renderSection = (title: string, items: any, indent: boolean = false) => (
      <>
        <tr className="table-secondary">
          <td colSpan={4} className="fw-bold">
            {title}:
          </td>
        </tr>
        {Object.entries(items).map(([key, value]: [string, any]) => {
          if (key === 'total_revenues' || key === 'total_expenditures' || 
              key === 'total_other_financing') {
            return (
              <tr key={value.code} className="table-primary fw-bold">
                <td>{value.code}</td>
                <td>{value.description}</td>
                <td className="text-end">{formatAmount(value.general_fund)}</td>
                <td className="text-end">{formatAmount(value.non_major_funds)}</td>
              </tr>
            )
          } else if (typeof value === 'object' && value.code && value.description !== undefined) {
            return renderFundRow(value)
          } else if (typeof value === 'object' && key === 'current') {
            return (
              <>
                <tr className="table-secondary">
                  <td className="ps-4 fw-bold">Current:</td>
                  <td></td>
                  <td></td>
                  <td></td>
                </tr>
                {Object.entries(value).map(([subKey, subValue]: [string, any]) => 
                  renderFundRow(subValue)
                )}
              </>
            )
          }
          return null
        })}
      </>
    )

    return (
      <div>
        <div className="text-center mb-3">
          <h4 className="mb-1">{data.title}</h4>
        </div>
        
        <Table striped hover className="mb-0">
          <thead>
            <tr>
              <th>Data Control Codes</th>
              <th>Description</th>
              <th className="text-end">{data.funds.general_fund}</th>
              <th className="text-end">{data.funds.non_major_funds}</th>
            </tr>
          </thead>
          <tbody>
            {renderSection('REVENUES', data.revenues)}
            {renderSection('EXPENDITURES', data.expenditures)}
            <tr className="table-primary fw-bold">
              <td>{data.excess_deficiency.code}</td>
              <td>{data.excess_deficiency.description}</td>
              <td className="text-end">{formatNetAmount(data.excess_deficiency.general_fund)}</td>
              <td className="text-end">{formatNetAmount(data.excess_deficiency.non_major_funds)}</td>
            </tr>
            {renderSection('Other Financing Sources and (Uses)', data.other_financing)}
            {renderNetRow(data.net_change)}
            {renderFundRow(data.fund_balances.beginning)}
            <tr className="table-primary fw-bold">
              <td>{data.fund_balances.ending.code}</td>
              <td>{data.fund_balances.ending.description}</td>
              <td className="text-end">{formatAmount(data.fund_balances.ending.general_fund)}</td>
              <td className="text-end">{formatAmount(data.fund_balances.ending.non_major_funds)}</td>
            </tr>
          </tbody>
        </Table>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="mb-0">
          📄 Financial Statements
        </h2>
      </div>

      {!mapping || Object.keys(mapping).length === 0 ? (
        <Alert variant="warning">
          ⚠️ Please upload data and configure account mapping before viewing financial statements.
        </Alert>
      ) : generating ? (
        <Alert variant="info">
          <Spinner animation="border" size="sm" className="me-2" />
          Generating financial statements...
        </Alert>
      ) : statements ? (
        <Alert variant="success">
          ✅ Financial statements generated successfully!
        </Alert>
      ) : (
        <Alert variant="info">
          ✅ Ready to generate statements automatically.
        </Alert>
      )}

      {statements ? (
        <>
          {/* Export Options Section */}
          <Card className="mb-4">
            <Card.Header>
              <h5 className="mb-0">📥 Export Options</h5>
            </Card.Header>
            <Card.Body>
              <Row>
                <Col lg={6} className="mb-3">
                  <div className="text-center">
                    <div className="mb-2">
                      <div style={{fontSize: '32px'}}>📊</div>
                    </div>
                    <h6>Export to Excel</h6>
                    <p className="text-muted small">
                      Download formatted financial statements as an Excel workbook with multiple worksheets
                    </p>
                    <Button 
                      variant="success" 
                      size="sm"
                      onClick={handleExportExcel}
                      disabled={exportingExcel}
                    >
                      📥
                      {exportingExcel ? 'Exporting...' : 'Download Excel'}
                    </Button>
                  </div>
                </Col>

                <Col lg={6} className="mb-3">
                  <div className="text-center">
                    <div className="mb-2">
                      <div style={{fontSize: '32px'}}>📄</div>
                    </div>
                    <h6>Export to PDF</h6>
                    <p className="text-muted small">
                      Generate PDF report with print-ready formatting for official submissions
                    </p>
                    <Button 
                      variant="danger" 
                      size="sm"
                      onClick={handlePrintPDF}
                    >
                      📥
                      Print to PDF
                    </Button>
                  </div>
                </Col>
              </Row>
            </Card.Body>
          </Card>

          {/* Financial Statements */}
          <Row>
            <Col lg={12} className="mb-4">
              <Card className="statement-section border border-primary">
                <Card.Header className="bg-primary text-white">
                  <h5 className="mb-0">
                    📊 Government-wide Statement of Net Position
                  </h5>
                </Card.Header>
                <Card.Body>
                  {renderNetPositionStatement(statements.government_wide_net_position)}
                </Card.Body>
              </Card>
            </Col>

            <Col lg={12} className="mb-4">
              <Card className="statement-section border border-success">
                <Card.Header className="bg-success text-white">
                  <h5 className="mb-0">
                    📈 Government-wide Statement of Activities
                  </h5>
                </Card.Header>
                <Card.Body>
                  {renderActivitiesStatement(statements.government_wide_activities)}
                </Card.Body>
              </Card>
            </Col>

            <Col lg={12} className="mb-4">
              <Card className="statement-section border border-warning">
                <Card.Header className="bg-warning text-dark">
                  <h5 className="mb-0">
                    💰 Governmental Funds Balance Sheet
                  </h5>
                </Card.Header>
                <Card.Body>
                  {renderBalanceSheetStatement(statements.governmental_funds_balance)}
                </Card.Body>
              </Card>
            </Col>

            <Col lg={12} className="mb-4">
              <Card className="statement-section border border-info">
                <Card.Header className="bg-info text-white">
                  <h5 className="mb-0">
                    📋 Statement of Revenues, Expenditures, and Changes in Fund Balances - Governmental Funds
                  </h5>
                </Card.Header>
                <Card.Body>
                  {renderRevenuesExpendituresStatement(statements.governmental_funds_revenues_expenditures)}
                </Card.Body>
              </Card>
            </Col>
          </Row>
        </>
      ) : (
        <Card>
          <Card.Body className="text-center py-5">
            <div className="text-muted mb-3" style={{fontSize: '48px'}}>📄</div>
            <h5>No Statements Available</h5>
            <p className="text-muted">
              Financial statements will be generated automatically when you navigate to this section, provided you have uploaded data and configured account mappings.
            </p>
          </Card.Body>
        </Card>
      )}
    </div>
  )
}