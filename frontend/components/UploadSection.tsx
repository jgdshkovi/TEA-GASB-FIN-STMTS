import { useState, useCallback } from 'react'
import { Card, Alert, ProgressBar, Row, Col } from 'react-bootstrap'
import { FiUpload, FiFile, FiCheckCircle } from 'react-icons/fi'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { uploadFile, getFileData, getMapping, saveMapping, autoMapAccounts, AutoMapResponse } from '../services/api'

interface FileInfo {
  filename: string
  encoding: string
  delimiter: string
  rows: number
  columns: number
}

interface UploadSectionProps {
  onNavigateToMapping?: () => void
}

// Helper function to convert delimiter to user-friendly text
const getDelimiterDisplayText = (delimiter: string): string => {
  switch (delimiter) {
    case '\t':
      return 'TAB'
    case ' ':
      return 'SPACE'
    case '  ':
      return 'DOUBLE SPACE'
    case ',':
      return 'COMMA'
    case '|':
      return 'PIPE'
    case ';':
      return 'SEMICOLON'
    default:
      // For other delimiters, show the character or a description
      if (delimiter.length === 1) {
        return `"${delimiter}"`
      }
      return delimiter
  }
}

export default function UploadSection({ onNavigateToMapping }: UploadSectionProps) {
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [autoMapping, setAutoMapping] = useState(false)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploading(true)
    setUploadProgress(0)

    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 10
        })
      }, 100)

      const response = await uploadFile(file)
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      if (response.success) {
        setFileInfo(response.file_info)
        toast.success('File uploaded successfully!')
        
        // Load the data
        const dataResponse = await getFileData()
        if (dataResponse.data) {
          toast.success(`Loaded ${dataResponse.data.length} records`)
        }
      } else {
        toast.error(response.message || 'Upload failed')
      }
    } catch (error) {
      toast.error('Error uploading file')
      console.error('Upload error:', error)
    } finally {
      setUploading(false)
      setTimeout(() => setUploadProgress(0), 1000)
    }
  }, [])

  const handleAutoMapAccounts = async () => {
    if (!fileInfo) {
      toast.error('Please upload a file first')
      return
    }

    setAutoMapping(true)
    try {
      // Call the auto-map endpoint to create mappings
      const response = await autoMapAccounts()
      
      if (response.success) {
        toast.success(`Auto-mapped ${Object.keys(response.mappings).length} accounts successfully!`)
        
        // Navigate to Account Mapping section
        if (onNavigateToMapping) {
          onNavigateToMapping()
        }
      } else {
        toast.error('Failed to auto-map accounts')
      }
      
    } catch (error) {
      toast.error('Error auto-mapping accounts')
      console.error('Error auto-mapping:', error)
    } finally {
      setAutoMapping(false)
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/plain': ['.txt', '.asc'],
      'text/csv': ['.csv'],
      'application/octet-stream': ['.txt', '.asc', '.csv'] // For files without extensions
    },
    maxSize: 25 * 1024 * 1024, // 25MB
    multiple: false
  })

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="mb-0">
          <FiUpload className="me-2" />
          Upload Trial Balance
        </h2>
      </div>

      <Alert variant="info" className="mb-4">
        <FiFile className="me-2" />
        Upload your ASCII trial balance file. The system will automatically detect the file format, 
        encoding, and delimiter. Supported formats: .txt, .csv, .asc, or files with no extension (max 25MB)
      </Alert>

      <Card>
        <Card.Body>
          <div
            {...getRootProps()}
            className={`upload-area ${isDragActive ? 'dragover' : ''}`}
          >
            <input {...getInputProps()} accept=".txt,.csv,.asc,*" />
            <FiUpload size={48} className="text-muted mb-3" />
            <h4>
              {isDragActive ? 'Drop the file here' : 'Drag & drop your file here'}
            </h4>
            <p className="text-muted mb-3">
              or click to browse your computer
            </p>
            <button 
              type="button" 
              className="btn btn-primary"
              disabled={uploading}
            >
              <FiUpload className="me-2" />
              Choose File
            </button>
          </div>

          {uploading && (
            <div className="mt-3">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <ProgressBar now={uploadProgress} animated />
            </div>
          )}

          {fileInfo && (
            <div className="file-info mt-4">
              <h5 className="mb-3">
                <FiCheckCircle className="me-2 text-success" />
                File Information
              </h5>
              <Row>
                <Col md={6}>
                  <p><strong>Filename:</strong> {fileInfo.filename}</p>
                  <p><strong>Encoding:</strong> {fileInfo.encoding.toUpperCase()}</p>
                  <p><strong>Delimiter:</strong> {getDelimiterDisplayText(fileInfo.delimiter)}</p>
                </Col>
                <Col md={6}>
                  <p><strong>Rows:</strong> {fileInfo.rows.toLocaleString()}</p>
                  <p><strong>Columns:</strong> {fileInfo.columns}</p>
                  <p><strong>Status:</strong> <span className="text-success">Ready for mapping</span></p>
                </Col>
              </Row>
              
              {/* Auto-Mapping Section */}
              <div className="mt-4 p-3 bg-light rounded">
                <h6 className="mb-3">🚀 Quick Setup</h6>
                <p className="text-muted mb-3">
                  Apply intelligent mapping defaults based on TEA standards to get started quickly.
                </p>
                <button 
                  className="btn btn-success"
                  onClick={handleAutoMapAccounts}
                  disabled={autoMapping}
                >
                  {autoMapping ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                      Auto-Mapping...
                    </>
                  ) : (
                    <>
                      🔄 Auto-Map Accounts
                    </>
                  )}
                </button>
                <small className="text-muted d-block mt-2">
                  This will take you to the Account Mapping section where intelligent defaults will be automatically applied to all your accounts.
                </small>
              </div>
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  )
}
