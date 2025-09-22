import axios from 'axios'

// Prefer explicit NEXT_PUBLIC_API_BASE_URL. Fallbacks: Render in prod, localhost in dev
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NODE_ENV === 'production'
    ? 'https://ggcpas.onrender.com'
    : 'http://localhost:8000')

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Get token from localStorage
const getToken = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('access_token')
  }
  return null
}

// Request interceptor to add auth headers
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('isAuthenticated')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export interface FileInfo {
  filename: string
  encoding: string
  delimiter: string
  rows: number
  columns: number
}

export interface UploadResponse {
  success: boolean
  message: string
  file_info: FileInfo
}

export interface DataResponse {
  data: any[]
  file_info: FileInfo
}

export interface MappingResponse {
  success: boolean
  message: string
  validation?: any
}

export interface PaginationInfo {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface PaginatedMappingResponse {
  mappings: Record<string, any>
  pagination: PaginationInfo
}

export interface AutoMapResponse {
  success: boolean
  message: string
  mappings: Record<string, any>
  pagination: PaginationInfo
}

export interface StatementResponse {
  success: boolean
  statements: any
}

export interface AuditTrailResponse {
  success: boolean
  audit_data: AuditTrailItem[]
  total_records: number
  file_info: {
    filename: string
    encoding: string
    delimiter: string
    rows: number
    columns: number
  }
}

export interface AuditTrailItem {
  // Original Trial Balance Data
  account_code: string
  current_year_actual: number
  budget: number
  prior_year_actual: number
  
  // Account Code Breakdown
  fund_code: string
  function_code: string
  object_code: string
  sub_object_code: string
  location_code: string
  unmapped_accounts: boolean
  
  // Mapping Categories
  tea_category: string
  gasb_category: string
  fund_category: string
  
  // Statement Mapping
  statement_type: string
  statement_section: string
  statement_line_code: string
  statement_line_description: string
  
  // Processing Information
  mapping_method: string
  mapping_confidence: string
  processing_notes: string
  rollup_applied: boolean
  rollup_description: string
  
  // Metadata
  file_upload_date: string
  processing_timestamp: string
  user_id: string
  version: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface RegisterRequest {
  email: string
  password: string
  first_name?: string
  last_name?: string
  organization?: string
}

export interface User {
  id: string
  email: string
  first_name?: string
  last_name?: string
  organization?: string
  is_active: boolean
  is_verified: boolean
}

// File upload
export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  
  return response.data
}

// Get uploaded data
export const getFileData = async (): Promise<DataResponse> => {
  const response = await api.get('/api/data')
  return response.data
}

// Get audit trail data with mappings
export const getAuditTrail = async (): Promise<AuditTrailResponse> => {
  const response = await api.get('/api/audit-trail')
  return response.data
}

// Get mapping configuration
export const getMapping = async (page: number = 1, pageSize: number = 100, search?: string): Promise<PaginatedMappingResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString()
  })
  
  if (search) {
    params.append('search', search)
  }
  
  const response = await api.get(`/api/mapping?${params}`)
  return response.data
}

// Save mapping configuration
export const saveMapping = async (mapping: any): Promise<MappingResponse> => {
  const response = await api.post('/api/mapping', mapping)
  return response.data
}

// Delete all mappings
export const deleteAllMappings = async (): Promise<MappingResponse> => {
  const response = await api.delete('/api/mapping')
  return response.data
}

// Auto-map accounts from trial balance data
export const autoMapAccounts = async (): Promise<AutoMapResponse> => {
  const response = await api.post('/api/mapping/auto-map')
  return response.data
}

// Generate financial statements
export const generateStatements = async (mapping: any): Promise<StatementResponse> => {
  const response = await api.post('/api/generate-statements', mapping)
  return response.data
}

// Export to Excel
export const exportToExcel = async (): Promise<Blob> => {
  const response = await api.get('/api/export/excel', {
    responseType: 'blob'
  })
  return response.data
}

// Export audit trail
export const exportAuditTrail = async (): Promise<Blob> => {
  const response = await api.get('/api/export/audit-trail', {
    responseType: 'blob'
  })
  return response.data
}

// Download file helper
export const downloadFile = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// Authentication API functions
export const login = async (credentials: LoginRequest): Promise<LoginResponse> => {
  const formData = new FormData()
  formData.append('username', credentials.username)
  formData.append('password', credentials.password)
  
  const response = await api.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  })
  
  return response.data
}

export const register = async (userData: RegisterRequest): Promise<User> => {
  const response = await api.post('/auth/register', userData)
  return response.data
}

export const getCurrentUser = async (): Promise<User> => {
  const response = await api.get('/auth/me')
  return response.data
}

export const logout = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token')
    localStorage.removeItem('isAuthenticated')
    window.location.href = '/login'
  }
}
