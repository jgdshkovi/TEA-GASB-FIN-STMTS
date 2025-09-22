import { useState, useEffect } from 'react'
import { Card, Alert, Button, Table, Form, Row, Col, InputGroup, Pagination } from 'react-bootstrap'
// Removed React Icons to prevent import errors
import toast from 'react-hot-toast'
import { getFileData, getMapping, saveMapping, deleteAllMappings as deleteAllMappingsAPI, autoMapAccounts, PaginationInfo } from '../services/api'

interface AccountMapping {
  account_code: string
  description: string
  tea_category: string
  gasb_category: string
  fund_category?: string
  statement_line?: string
  notes?: string
}

const TEA_CATEGORIES = [
  { value: 'Assets', label: 'Assets' },
  { value: 'Liabilities', label: 'Liabilities' },
  { value: 'Fund Balances/Net Position', label: 'Fund Balances/Net Position' },
  { value: 'Clearing Accounts', label: 'Clearing Accounts' },
  { value: 'Revenues', label: 'Revenues' },
  { value: 'Expenditures/Expenses', label: 'Expenditures/Expenses' },
  { value: 'Other Resources/Non-operating Revenues', label: 'Other Resources/Non-operating Revenues' },
  { value: 'Other Uses/Non-operating Expenses', label: 'Other Uses/Non-operating Expenses' }
]

const GASB_CATEGORIES = [
  { value: 'current_assets', label: 'Current Assets' },
  { value: 'capital_assets', label: 'Capital Assets' },
  { value: 'deferred_outflows', label: 'Deferred Outflows of Resources' },
  { value: 'current_liabilities', label: 'Current Liabilities' },
  { value: 'long_term_liabilities', label: 'Long-term Liabilities' },
  { value: 'deferred_inflows', label: 'Deferred Inflows of Resources' },
  { value: 'net_investment_capital_assets', label: 'Net Investment in Capital Assets' },
  { value: 'restricted_net_position', label: 'Restricted Net Position' },
  { value: 'unrestricted_net_position', label: 'Unrestricted Net Position' },
  { value: 'program_revenues', label: 'Program Revenues' },
  { value: 'general_revenues', label: 'General Revenues' },
  { value: 'program_expenses', label: 'Program Expenses' },
  { value: 'general_expenses', label: 'General Expenses' },
  { value: 'other_resources', label: 'Other Resources & Non-operating Revenues' },
  { value: 'other_uses', label: 'Other Uses & Non-operating Expenses' }
]

interface MappingSectionProps {
  loadTrigger?: boolean
  onLoadComplete?: () => void
}

export default function MappingSection({ loadTrigger = false, onLoadComplete }: MappingSectionProps) {
  const [mappings, setMappings] = useState<AccountMapping[]>([])
  const [originalMappings, setOriginalMappings] = useState<AccountMapping[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    page_size: 100,
    total_items: 0,
    total_pages: 0
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [searchInput, setSearchInput] = useState('')

  // Helper function to auto-map categories for an account code
  const autoMapCategories = (accountCode: string, existingTeaCategory?: string, existingGasbCategory?: string) => {
    if (accountCode.length < 9) {
      return { teaCategory: existingTeaCategory || 'Unknown', gasbCategory: existingGasbCategory || 'unknown' }
    }

    const objectCode = accountCode.substring(5, 9)
    const firstDigit = objectCode[0]
    
    // Auto-map TEA category if missing
    let teaCategory = existingTeaCategory
    if (!teaCategory) {
      const teaCategories = {
        '1': 'Assets',
        '2': 'Liabilities', 
        '3': 'Fund Balances/Net Position',
        '4': 'Clearing Accounts',
        '5': 'Revenues',
        '6': 'Expenditures/Expenses',
        '7': 'Other Resources/Non-operating Revenues',
        '8': 'Other Uses/Non-operating Expenses'
      }
      teaCategory = teaCategories[firstDigit] || 'Unknown'
    }
    
    // Auto-map GASB category if missing
    let gasbCategory = existingGasbCategory
    if (!gasbCategory) {
      if (firstDigit === '1') {
        gasbCategory = (objectCode.startsWith('11') || objectCode.startsWith('12') || objectCode.startsWith('13') || objectCode.startsWith('14')) ? 'current_assets' : 'capital_assets'
      } else if (firstDigit === '2') {
        gasbCategory = (objectCode.startsWith('21') || objectCode.startsWith('22') || objectCode.startsWith('23')) ? 'current_liabilities' : 'long_term_liabilities'
      } else if (firstDigit === '3') {
        if (objectCode.startsWith('32')) {
          gasbCategory = 'net_investment_capital_assets'
        } else if (objectCode.startsWith('33') || objectCode.startsWith('34') || objectCode.startsWith('35') || objectCode.startsWith('36') || objectCode.startsWith('37') || objectCode.startsWith('38')) {
          gasbCategory = 'restricted_net_position'
        } else {
          gasbCategory = 'unrestricted_net_position'
        }
      } else if (firstDigit === '5') {
        gasbCategory = (objectCode.startsWith('51') || objectCode.startsWith('52') || objectCode.startsWith('53')) ? 'program_revenues' : 'general_revenues'
      } else if (firstDigit === '6') {
        gasbCategory = (objectCode.startsWith('61') || objectCode.startsWith('62') || objectCode.startsWith('63') || objectCode.startsWith('64') || objectCode.startsWith('65')) ? 'program_expenses' : 'general_expenses'
      } else if (firstDigit === '7') {
        gasbCategory = 'other_resources'
      } else if (firstDigit === '8') {
        gasbCategory = 'other_uses'
      } else {
        gasbCategory = 'unknown'
      }
    }
    
    return { teaCategory, gasbCategory }
  }

  useEffect(() => {
    // Load data when component mounts or when pagination/search changes
    loadData()
  }, [currentPage, pageSize, searchTerm])

  // Handle load trigger from Upload section
  useEffect(() => {
    if (loadTrigger) {
      loadData()
      if (onLoadComplete) {
        onLoadComplete()
      }
    }
  }, [loadTrigger])

  const loadData = async () => {
    setLoading(true)
    try {
      const mappingResponse = await getMapping(currentPage, pageSize, searchTerm || undefined)

      // Convert the paginated mappings from the API response to array format
      const paginatedMappings = Object.values(mappingResponse.mappings || {}) as AccountMapping[]
      
      setMappings(paginatedMappings)
      setOriginalMappings(paginatedMappings) // Store original state for comparison
      setPagination(mappingResponse.pagination)
    } catch (error) {
      toast.error('Error loading data')
      console.error('Error loading data:', error)
    } finally {
      setLoading(false)
    }
  }

  const updateMapping = (index: number, field: keyof AccountMapping, value: string) => {
    // Update local state only - do not save to backend
    setMappings(prev => prev.map((mapping, i) => 
      i === index ? { ...mapping, [field]: value } : mapping
    ))
  }

  const removeMapping = (index: number) => {
    // Remove from local state only - do not save to backend
    setMappings(prev => prev.filter((_, i) => i !== index))
  }

  const clearAllMappings = async () => {
    try {
      // Only reset mappings for accounts that are currently loaded (not recreate from trial balance)
      if (mappings.length === 0) {
        toast.error('No mappings to reset. Please load mappings first.')
        return
      }

      // Create fresh auto-mapped mappings for only the currently loaded account codes
      const freshMappings = mappings.map((existingMapping) => {
        const accountCode = existingMapping.account_code
        const description = existingMapping.description
        
        // Apply mapping rules using the same logic as the backend
        const fundCode = accountCode.substring(0, 3)
        const objectCode = accountCode.substring(5, 9)
        
        // Get TEA category from object code (first digit)
        const firstDigit = objectCode[0]
        const teaCategories = {
          '1': 'Assets',
          '2': 'Liabilities', 
          '3': 'Fund Balances/Net Position',
          '4': 'Clearing Accounts',
          '5': 'Revenues',
          '6': 'Expenditures/Expenses',
          '7': 'Other Resources/Non-operating Revenues',
          '8': 'Other Uses/Non-operating Expenses'
        }
        const teaCategory = teaCategories[firstDigit] || 'Unknown'
        
        // Get GASB category (simplified mapping - same as backend logic)
        let gasbCategory = 'unknown'
        if (firstDigit === '1') {
          gasbCategory = (objectCode.startsWith('11') || objectCode.startsWith('12') || objectCode.startsWith('13') || objectCode.startsWith('14')) ? 'current_assets' : 'capital_assets'
        } else if (firstDigit === '2') {
          gasbCategory = (objectCode.startsWith('21') || objectCode.startsWith('22') || objectCode.startsWith('23')) ? 'current_liabilities' : 'long_term_liabilities'
        } else if (firstDigit === '3') {
          if (objectCode.startsWith('32')) {
            gasbCategory = 'net_investment_capital_assets'
          } else if (objectCode.startsWith('33') || objectCode.startsWith('34') || objectCode.startsWith('35') || objectCode.startsWith('36') || objectCode.startsWith('37') || objectCode.startsWith('38')) {
            gasbCategory = 'restricted_net_position'
          } else {
            gasbCategory = 'unrestricted_net_position'
          }
        } else if (firstDigit === '5') {
          gasbCategory = (objectCode.startsWith('51') || objectCode.startsWith('52') || objectCode.startsWith('53')) ? 'program_revenues' : 'general_revenues'
        } else if (firstDigit === '6') {
          gasbCategory = (objectCode.startsWith('61') || objectCode.startsWith('62') || objectCode.startsWith('63') || objectCode.startsWith('64') || objectCode.startsWith('65')) ? 'program_expenses' : 'general_expenses'
        } else if (firstDigit === '7') {
          gasbCategory = 'other_resources'
        } else if (firstDigit === '8') {
          gasbCategory = 'other_uses'
        }
        
        // Get fund category (simplified)
        const fundCategories = {
          '199': 'general_fund',
          '200': 'special_revenue_funds',
          '300': 'debt_service_funds',
          '400': 'capital_projects_funds',
          '500': 'enterprise_funds',
          '600': 'internal_service_funds',
          '700': 'trust_and_agency_funds'
        }
        const fundCategory = fundCategories[fundCode] || 'other_governmental_funds'
        
        return {
          account_code: accountCode,
          description: description,
          tea_category: teaCategory,
          gasb_category: gasbCategory,
          fund_category: fundCategory,
          statement_line: 'XX',
          notes: ''
        }
      })

      // Save the fresh auto-mapped mappings to the database
      const mappingObject = freshMappings.reduce((acc, mapping) => {
        acc[mapping.account_code] = mapping
        return acc
      }, {} as Record<string, AccountMapping>)

      const response = await saveMapping(mappingObject)
      if (response.success) {
        toast.success(`Reset and auto-mapped ${freshMappings.length} accounts successfully!`)
        
        // Refresh data from backend after successful save
        await loadData()
        
        if (response.validation) {
          if (response.validation.valid) {
            toast.success('All accounts have been mapped!')
          } else {
            // Show helpful message about unmapped accounts
            const unmappedCount = response.validation.total_unmapped
            const unmappedAccounts = response.validation.unmapped_accounts || []
            
            if (unmappedCount > 0) {
              toast.error(`⚠️ ${unmappedCount} account(s) still need GASB category mapping. Examples: ${unmappedAccounts.slice(0, 3).join(', ')}${unmappedCount > 3 ? '...' : ''}`, {
                icon: '⚠️',
                duration: 5000,
                style: {
                  background: '#fff3cd',
                  color: '#856404',
                  border: '1px solid #ffeaa7'
                }
              })
            }
          }
          
          // Show warnings about missing essential categories
          if (response.validation.warnings && response.validation.warnings.length > 0) {
            toast(`💡 Consider adding: ${response.validation.warnings.join(', ')}`, {
              icon: '💡',
              duration: 5000,
              style: {
                background: '#d1ecf1',
                color: '#0c5460',
                border: '1px solid #bee5eb'
              }
            })
          }
        }
      } else {
        toast.error('Failed to reset and auto-map accounts')
      }
    } catch (error) {
      toast.error('Error resetting and auto-mapping accounts')
      console.error('Error resetting and auto-mapping:', error)
    }
  }

  const deleteAllMappings = async () => {
    // Show confirmation dialog
    const confirmed = window.confirm(
      '⚠️ WARNING: This will permanently delete ALL mappings from the database.\n\n' +
      'This action cannot be undone. Are you sure you want to continue?'
    )
    
    if (!confirmed) {
      return
    }

    try {
      // Delete all mappings from database using dedicated delete endpoint
      const response = await deleteAllMappingsAPI()
      
      if (response.success) {
        // Clear local state - don't reload data, just show empty table
        setMappings([])
        setOriginalMappings([])
        
        // Reset pagination to show empty state
        setPagination({
          page: 1,
          page_size: pageSize,
          total_items: 0,
          total_pages: 0
        })
        
        toast.success('All mappings permanently deleted from database!')
      } else {
        toast.error('Failed to delete mappings from database')
      }
    } catch (error) {
      toast.error('Error deleting all mappings')
      console.error('Error deleting all mappings:', error)
    }
  }

  const saveMappings = async () => {
    setSaving(true)
    try {
      // Create mapping object with current mappings, auto-mapping missing categories
      const mappingObject = mappings.reduce((acc, mapping) => {
        // Auto-map missing categories before saving
        const { teaCategory, gasbCategory } = autoMapCategories(
          mapping.account_code, 
          mapping.tea_category, 
          mapping.gasb_category
        )
        
        acc[mapping.account_code] = {
          ...mapping,
          tea_category: teaCategory,
          gasb_category: gasbCategory
        }
        return acc
      }, {} as Record<string, AccountMapping>)

      // Find removed mappings (in original but not in current)
      const originalAccountCodes = new Set(originalMappings.map(m => m.account_code))
      const currentAccountCodes = new Set(mappings.map(m => m.account_code))
      
      // Add null values for removed mappings
      originalAccountCodes.forEach(accountCode => {
        if (!currentAccountCodes.has(accountCode)) {
          mappingObject[accountCode] = null as any // This will be handled as deletion by backend
        }
      })

      const response = await saveMapping(mappingObject)
      if (response.success) {
        toast.success('Mapping saved successfully!')
        
        // Refresh data from backend after successful save
        await loadData()
        
        if (response.validation) {
          if (response.validation.valid) {
            toast.success('All accounts have been mapped!')
          } else {
            // Show helpful message about unmapped accounts
            const unmappedCount = response.validation.total_unmapped
            const unmappedAccounts = response.validation.unmapped_accounts || []
            
            if (unmappedCount > 0) {
              toast.error(`⚠️ ${unmappedCount} account(s) still need GASB category mapping. Examples: ${unmappedAccounts.slice(0, 3).join(', ')}${unmappedCount > 3 ? '...' : ''}`, {
                icon: '⚠️',
                duration: 5000,
                style: {
                  background: '#fff3cd',
                  color: '#856404',
                  border: '1px solid #ffeaa7'
                }
              })
            }
          }
          
          // Show warnings about missing essential categories
          if (response.validation.warnings && response.validation.warnings.length > 0) {
            toast(`💡 Consider adding: ${response.validation.warnings.join(', ')}`, {
              icon: '💡',
              duration: 5000,
              style: {
                background: '#d1ecf1',
                color: '#0c5460',
                border: '1px solid #bee5eb'
              }
            })
          }
        }
      }
    } catch (error) {
      toast.error('Error saving mapping')
      console.error('Error saving mapping:', error)
    } finally {
      setSaving(false)
    }
  }

  const resetAndAutoMap = async () => {
    try {
      // Only reset mappings for accounts that are currently loaded (not recreate from trial balance)
      if (mappings.length === 0) {
        toast.error('No mappings to reset. Please load mappings first.')
        return
      }

      // Create fresh auto-mapped mappings for only the currently loaded account codes
      const freshMappings = mappings.map((existingMapping) => {
        const accountCode = existingMapping.account_code
        const description = existingMapping.description
        
        // Apply mapping rules using the same logic as the backend
        const fundCode = accountCode.substring(0, 3)
        const objectCode = accountCode.substring(5, 9)
        
        // Get TEA category from object code (first digit)
        const firstDigit = objectCode[0]
        const teaCategories = {
          '1': 'Assets',
          '2': 'Liabilities', 
          '3': 'Fund Balances/Net Position',
          '4': 'Clearing Accounts',
          '5': 'Revenues',
          '6': 'Expenditures/Expenses',
          '7': 'Other Resources/Non-operating Revenues',
          '8': 'Other Uses/Non-operating Expenses'
        }
        const teaCategory = teaCategories[firstDigit] || 'Unknown'
        
        // Get GASB category (simplified mapping - same as backend logic)
        let gasbCategory = 'unknown'
        if (firstDigit === '1') {
          gasbCategory = (objectCode.startsWith('11') || objectCode.startsWith('12') || objectCode.startsWith('13') || objectCode.startsWith('14')) ? 'current_assets' : 'capital_assets'
        } else if (firstDigit === '2') {
          gasbCategory = (objectCode.startsWith('21') || objectCode.startsWith('22') || objectCode.startsWith('23')) ? 'current_liabilities' : 'long_term_liabilities'
        } else if (firstDigit === '3') {
          if (objectCode.startsWith('32')) {
            gasbCategory = 'net_investment_capital_assets'
          } else if (objectCode.startsWith('33') || objectCode.startsWith('34') || objectCode.startsWith('35') || objectCode.startsWith('36') || objectCode.startsWith('37') || objectCode.startsWith('38')) {
            gasbCategory = 'restricted_net_position'
          } else {
            gasbCategory = 'unrestricted_net_position'
          }
        } else if (firstDigit === '5') {
          gasbCategory = (objectCode.startsWith('51') || objectCode.startsWith('52') || objectCode.startsWith('53')) ? 'program_revenues' : 'general_revenues'
        } else if (firstDigit === '6') {
          gasbCategory = (objectCode.startsWith('61') || objectCode.startsWith('62') || objectCode.startsWith('63') || objectCode.startsWith('64') || objectCode.startsWith('65')) ? 'program_expenses' : 'general_expenses'
        } else if (firstDigit === '7') {
          gasbCategory = 'other_resources'
        } else if (firstDigit === '8') {
          gasbCategory = 'other_uses'
        }
        
        // Get fund category (simplified)
        const fundCategories = {
          '199': 'general_fund',
          '200': 'special_revenue_funds',
          '300': 'debt_service_funds',
          '400': 'capital_projects_funds',
          '500': 'enterprise_funds',
          '600': 'internal_service_funds',
          '700': 'trust_and_agency_funds'
        }
        const fundCategory = fundCategories[fundCode] || 'other_governmental_funds'
        
        return {
          account_code: accountCode,
          description: description,
          tea_category: teaCategory,
          gasb_category: gasbCategory,
          fund_category: fundCategory,
          statement_line: 'XX',
          notes: ''
        }
      })

      // Update the local state with fresh mappings (not saved to database yet)
      setMappings(freshMappings)
      setOriginalMappings(freshMappings) // Update original state to match current
      
      toast.success(`Reset completed! Fresh auto-mapping applied to ${freshMappings.length} accounts (not saved).`)
    } catch (error) {
      toast.error('Error resetting and auto-mapping')
      console.error('Error resetting and auto-mapping:', error)
    }
  }

  const exportMapping = () => {
    const csvContent = [
      'Account Code,Description,TEA Category,GASB Category,Fund Category,Statement Line,Notes',
      ...mappings.map(m => `${m.account_code},"${m.description}",${m.tea_category},${m.gasb_category},${m.fund_category || ''},${m.statement_line || 'XX'},${m.notes || ''}`)
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'account_mapping.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      setSelectedFile(null)
      return
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      toast.error('Please select a CSV file')
      setSelectedFile(null)
      return
    }

    setSelectedFile(file)
    toast.success(`File selected: ${file.name}`)
  }

  const handleFileUpload = async () => {
    if (!selectedFile) {
      toast.error('Please select a CSV file first')
      return
    }

    setUploading(true)
    try {
      const text = await selectedFile.text()
      const lines = text.split('\n').filter(line => line.trim())
      
      if (lines.length < 2) {
        toast.error('CSV file must have at least a header and one data row')
        return
      }

      // Parse CSV header
      const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''))
      const expectedHeaders = ['Account Code', 'Description', 'TEA Category', 'GASB Category', 'Fund Category', 'Statement Line', 'Notes']
      
      // Check if headers match expected format
      if (!expectedHeaders.every(header => headers.includes(header))) {
        toast.error('CSV headers must include: Account Code, Description, TEA Category, GASB Category, Fund Category, Statement Line, Notes')
        return
      }

      // Parse CSV data and apply auto-mapping for missing/incorrect categories
      const csvMappings: AccountMapping[] = []
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''))
        if (values.length >= 4) { // At least account code, description, TEA category, GASB category
          const accountCode = values[0] || ''
          const description = values[1] || ''
          let teaCategory = values[2] || ''
          let gasbCategory = values[3] || ''
          const fundCategory = values[4] || ''
          const statementLine = values[5] || 'XX'
          const notes = values[6] || ''
          
          // Auto-map missing categories using helper function
          const { teaCategory: autoTeaCategory, gasbCategory: autoGasbCategory } = autoMapCategories(
            accountCode, 
            teaCategory || undefined, 
            gasbCategory || undefined
          )
          
          // Use auto-mapped categories if original was missing
          teaCategory = teaCategory || autoTeaCategory
          gasbCategory = gasbCategory || autoGasbCategory
          
          csvMappings.push({
            account_code: accountCode,
            description: description,
            tea_category: teaCategory,
            gasb_category: gasbCategory,
            fund_category: fundCategory,
            statement_line: statementLine,
            notes: notes
          })
        }
      }

      if (csvMappings.length === 0) {
        toast.error('No valid mapping data found in CSV file')
        return
      }

      // Merge with existing mappings
      const existingMappings = mappings.reduce((acc, mapping) => {
        acc[mapping.account_code] = mapping
        return acc
      }, {} as Record<string, AccountMapping>)

      const mergedMappings = csvMappings.map(csvMapping => ({
        ...existingMappings[csvMapping.account_code], // Keep existing data for fields not in CSV
        ...csvMapping // Override with CSV data
      }))

      setMappings(mergedMappings)
      
      // Save the uploaded mappings to the backend
      try {
        const mappingObject = mergedMappings.reduce((acc, mapping) => {
          acc[mapping.account_code] = mapping
          return acc
        }, {} as Record<string, AccountMapping>)

        const saveResponse = await saveMapping(mappingObject)
        if (saveResponse.success) {
          toast.success(`Successfully imported and saved ${csvMappings.length} mappings from CSV!`)
          
          // Refresh data from backend after successful save
          await loadData()
          
          if (saveResponse.validation) {
            if (saveResponse.validation.valid) {
              toast.success('All accounts have been mapped!')
            } else {
              // Show helpful message about unmapped accounts
              const unmappedCount = saveResponse.validation.total_unmapped
              const unmappedAccounts = saveResponse.validation.unmapped_accounts || []
              
              if (unmappedCount > 0) {
                toast.error(`⚠️ ${unmappedCount} account(s) still need GASB category mapping. Examples: ${unmappedAccounts.slice(0, 3).join(', ')}${unmappedCount > 3 ? '...' : ''}`, {
                  icon: '⚠️',
                  duration: 5000,
                  style: {
                    background: '#fff3cd',
                    color: '#856404',
                    border: '1px solid #ffeaa7'
                  }
                })
              }
            }
            
            // Show warnings about missing essential categories
            if (saveResponse.validation.warnings && saveResponse.validation.warnings.length > 0) {
              toast(`💡 Consider adding: ${saveResponse.validation.warnings.join(', ')}`, {
                icon: '💡',
                duration: 5000,
                style: {
                  background: '#d1ecf1',
                  color: '#0c5460',
                  border: '1px solid #bee5eb'
                }
              })
            }
          }
        } else {
          toast.error('Failed to save uploaded mappings to backend')
        }
      } catch (saveError) {
        toast.error('Error saving uploaded mappings to backend')
        console.error('Error saving uploaded mappings:', saveError)
      }
      
      // Clear the selected file after successful upload
      setSelectedFile(null)
      
    } catch (error) {
      toast.error('Error reading CSV file')
      console.error('Error reading CSV:', error)
    } finally {
      setUploading(false)
    }
  }

  // Pagination handlers
  const handlePageChange = (page: number) => {
    setCurrentPage(page)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setCurrentPage(1) // Reset to first page when changing page size
  }

  const handleSearch = () => {
    setSearchTerm(searchInput)
    setCurrentPage(1) // Reset to first page when searching
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  // Generate page numbers for pagination
  const generatePageNumbers = () => {
    const pages = []
    const totalPages = pagination.total_pages
    const current = pagination.page
    
    // Always show first page
    if (totalPages > 0) {
      pages.push(1)
    }
    
    // Show pages around current page
    const start = Math.max(2, current - 2)
    const end = Math.min(totalPages - 1, current + 2)
    
    if (start > 2) {
      pages.push('...')
    }
    
    for (let i = start; i <= end; i++) {
      if (i !== 1 && i !== totalPages) {
        pages.push(i)
      }
    }
    
    if (end < totalPages - 1) {
      pages.push('...')
    }
    
    // Always show last page
    if (totalPages > 1) {
      pages.push(totalPages)
    }
    
    return pages
  }

  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
        <p className="mt-3">Loading mapping data...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="mb-0">
          🗺️ Account Mapping
        </h2>
      </div>

      <Alert variant="info" className="mb-4">
        🗺️ Map your account codes to TEA/GASB categories. You can edit the mapping table below, 
        use auto-mapping, or upload a CSV file with your mappings.
      </Alert>

      <Row className="mb-4">
        <Col md={6}>
          <Card>
            <Card.Body>
              <h6>Quick Actions</h6>
              <Button variant="success" className="me-2 mb-2" onClick={saveMappings} disabled={saving}>
                💾 {saving ? 'Saving...' : 'Save Mapping'}
              </Button>
              <Button variant="outline-primary" className="me-2 mb-2" onClick={exportMapping}>
                📥 Export Mapping
              </Button>
              <Button variant="warning" className="me-2 mb-2" onClick={clearAllMappings}>
                🔄 Reset & Auto-Map
              </Button>
              <Button variant="danger" className="mb-2" onClick={deleteAllMappings}>
                🗑️ Delete All
              </Button>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6}>
          <Card>
            <Card.Body>
              <h6>Upload Mapping CSV</h6>
              <InputGroup>
                <Form.Control 
                  type="file" 
                  accept=".csv" 
                  onChange={handleFileSelect}
                  disabled={uploading}
                />
                <Button 
                  variant="success" 
                  disabled={uploading || !selectedFile}
                  onClick={handleFileUpload}
                >
                  📤 {uploading ? 'Uploading...' : 'Upload & Save'}
                </Button>
              </InputGroup>
              {selectedFile && (
                <small className="text-muted mt-2 d-block">
                  Selected: {selectedFile.name}
                </small>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Search and Pagination Controls */}
      <Row className="mb-3">
        <Col md={6}>
          <InputGroup>
            <Form.Control
              type="text"
              placeholder="Search account codes, descriptions, or categories..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyPress={handleKeyPress}
            />
            <Button 
              variant="outline-secondary" 
              onClick={handleSearch}
              title="Search"
            >
              🔍
            </Button>
          </InputGroup>
        </Col>
        <Col md={6} className="d-flex justify-content-end align-items-center">
          <div className="d-flex align-items-center">
            <span className="me-2">Items per page:</span>
            <Form.Select
              size="sm"
              style={{ width: '80px' }}
              value={pageSize}
              onChange={(e) => handlePageSizeChange(Number(e.target.value))}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </Form.Select>
          </div>
        </Col>
      </Row>

      {/* Pagination Info */}
      {pagination.total_items > 0 && (
        <Row className="mb-3">
          <Col>
            <small className="text-muted">
              Showing {((pagination.page - 1) * pagination.page_size) + 1} to {Math.min(pagination.page * pagination.page_size, pagination.total_items)} of {pagination.total_items.toLocaleString()} items
            </small>
          </Col>
        </Row>
      )}

      {/* Top Pagination Controls */}
      {pagination.total_pages > 1 && (
        <div className="d-flex justify-content-center mb-3">
          <Pagination>
            <Pagination.First 
              onClick={() => handlePageChange(1)}
              disabled={pagination.page === 1}
            />
            <Pagination.Prev 
              onClick={() => handlePageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
            />
            
            {generatePageNumbers().map((page, index) => (
              <Pagination.Item
                key={index}
                active={page === pagination.page}
                onClick={() => typeof page === 'number' ? handlePageChange(page) : undefined}
                disabled={page === '...'}
              >
                {page}
              </Pagination.Item>
            ))}
            
            <Pagination.Next 
              onClick={() => handlePageChange(pagination.page + 1)}
              disabled={pagination.page === pagination.total_pages}
            />
            <Pagination.Last 
              onClick={() => handlePageChange(pagination.total_pages)}
              disabled={pagination.page === pagination.total_pages}
            />
          </Pagination>
        </div>
      )}

      <Card>
        <Card.Body>
          <div className="table-responsive">
            <Table striped hover>
              <thead>
                <tr>
                  <th>Account Code</th>
                  <th>Description</th>
                  <th>TEA Category</th>
                  <th>GASB Category</th>
                  <th>Fund Category</th>
                  <th>Statement Line</th>
                  <th>Notes</th>
                  <th style={{width: '100px'}}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((mapping, index) => (
                  <tr key={mapping.account_code}>
                    <td>
                      <strong>{mapping.account_code}</strong>
                    </td>
                    <td>
                      <Form.Control
                        type="text"
                        size="sm"
                        placeholder="Enter description"
                        value={mapping.description}
                        onChange={(e) => updateMapping(index, 'description', e.target.value)}
                      />
                    </td>
                    <td>
                      <Form.Select
                        size="sm"
                        value={mapping.tea_category}
                        onChange={(e) => updateMapping(index, 'tea_category', e.target.value)}
                      >
                        <option value="">Select TEA Category</option>
                        {TEA_CATEGORIES.map(cat => (
                          <option key={cat.value} value={cat.value}>
                            {cat.label}
                          </option>
                        ))}
                      </Form.Select>
                    </td>
                    <td>
                      <Form.Select
                        size="sm"
                        value={mapping.gasb_category}
                        onChange={(e) => updateMapping(index, 'gasb_category', e.target.value)}
                      >
                        <option value="">Select GASB Category</option>
                        {GASB_CATEGORIES.map(cat => (
                          <option key={cat.value} value={cat.value}>
                            {cat.label}
                          </option>
                        ))}
                      </Form.Select>
                    </td>
                    <td>
                      <Form.Control
                        type="text"
                        size="sm"
                        placeholder="Fund category"
                        value={mapping.fund_category || ''}
                        onChange={(e) => updateMapping(index, 'fund_category', e.target.value)}
                      />
                    </td>
                    <td>
                      <Form.Control
                        type="text"
                        size="sm"
                        placeholder="Statement line"
                        value={mapping.statement_line || 'XX'}
                        onChange={(e) => updateMapping(index, 'statement_line', e.target.value)}
                      />
                    </td>
                    <td>
                      <Form.Control
                        type="text"
                        size="sm"
                        placeholder="Notes"
                        value={mapping.notes || ''}
                        onChange={(e) => updateMapping(index, 'notes', e.target.value)}
                      />
                    </td>
                    <td>
                      <Button
                        variant="outline-danger"
                        size="sm"
                        onClick={() => removeMapping(index)}
                      >
                        🗑️
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>

          {mappings.length === 0 && (
            <div className="text-center py-4 text-muted">
              No mappings available. Please upload a trial balance file first.
            </div>
          )}
        </Card.Body>
      </Card>

      {/* Pagination Controls */}
      {pagination.total_pages > 1 && (
        <div className="d-flex justify-content-center mt-4">
          <Pagination>
            <Pagination.First 
              onClick={() => handlePageChange(1)}
              disabled={pagination.page === 1}
            />
            <Pagination.Prev 
              onClick={() => handlePageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
            />
            
            {generatePageNumbers().map((page, index) => (
              <Pagination.Item
                key={index}
                active={page === pagination.page}
                onClick={() => typeof page === 'number' ? handlePageChange(page) : undefined}
                disabled={page === '...'}
              >
                {page}
              </Pagination.Item>
            ))}
            
            <Pagination.Next 
              onClick={() => handlePageChange(pagination.page + 1)}
              disabled={pagination.page === pagination.total_pages}
            />
            <Pagination.Last 
              onClick={() => handlePageChange(pagination.total_pages)}
              disabled={pagination.page === pagination.total_pages}
            />
          </Pagination>
        </div>
      )}
    </div>
  )
}
