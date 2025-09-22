from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import json
import csv
import io
from datetime import datetime
import chardet
import re
from pathlib import Path
import secrets
from typing import Optional, Dict, Any
import uvicorn
from mapping_rules import create_default_mapping, get_tea_category, get_gasb_category, get_fund_category, validate_mapping

# Simple authentication imports
from simple_auth_endpoints import (
    router as auth_router, 
    get_current_user, 
    init_db,
    save_trial_balance_data,
    get_trial_balance_data,
    save_account_mappings,
    get_account_mappings,
    save_financial_statements,
    get_financial_statements,
    save_audit_trail,
    get_audit_trail,
    clear_audit_trail
)

app = FastAPI(title="TEA Financial Statement Generator", version="1.0.0")

# Security
security = HTTPBasic()

# Demo credentials (temporary - for backward compatibility)
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"

# Session storage (in-memory)
session_data = {}

# Initialize database
init_db()

# Configuration
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {".txt", ".csv", ".asc", ""}  # Empty string for files with no extension
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo (in production, use a database)
session_data: Dict[str, Any] = {}

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify user credentials - DISABLED FOR DEVELOPMENT"""
    # TODO: Re-enable authentication for production
    # is_correct_username = secrets.compare_digest(credentials.username, DEMO_USERNAME)
    # is_correct_password = secrets.compare_digest(credentials.password, DEMO_PASSWORD)
    
    # if not (is_correct_username and is_correct_password):
    #     raise HTTPException(
    #         status_code=401,
    #         detail="Incorrect username or password",
    #         headers={"WWW-Authenticate": "Basic"},
    #     )
    # return credentials.username
    
    # For development - always return demo user
    return "demo"

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    # Allow files with no extension (common for ASCII files)
    if not Path(filename).suffix:
        return True
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def detect_encoding_and_delimiter(file_path: str) -> tuple[str, str]:
    """Auto-detect file encoding and delimiter with improved logic"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    
    # Detect encoding
    encoding_result = chardet.detect(raw_data)
    encoding = encoding_result['encoding'] or 'utf-8'
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            # Read first 20 lines for better analysis
            lines = []
            for i, line in enumerate(f):
                if i >= 20:
                    break
                lines.append(line.strip())
        
        # Test different delimiters
        delimiters = ['\t', ',', '|', ';', '  ', ' ']  # Added double space and single space
        delimiter_scores = {}
        
        for delimiter in delimiters:
            column_counts = []
            consistent = True
            
            for line in lines:
                if line.strip():  # Skip empty lines
                    parts = line.split(delimiter)
                    # Filter out empty parts for space delimiters
                    if delimiter == ' ' or delimiter == '  ':
                        parts = [part for part in parts if part.strip()]
                    
                    column_counts.append(len(parts))
            
            if column_counts:
                # Check consistency (all lines should have same number of columns)
                if len(set(column_counts)) == 1 and column_counts[0] > 1:
                    delimiter_scores[delimiter] = {
                        'columns': column_counts[0],
                        'consistency': 1.0,
                        'sample_line': lines[0] if lines else ''
                    }
                elif column_counts:
                    # Calculate consistency score
                    most_common = max(set(column_counts), key=column_counts.count)
                    consistency = column_counts.count(most_common) / len(column_counts)
                    if consistency > 0.8 and most_common > 1:  # 80% consistency threshold
                        delimiter_scores[delimiter] = {
                            'columns': most_common,
                            'consistency': consistency,
                            'sample_line': lines[0] if lines else ''
                        }
        
        # Choose best delimiter based on consistency and column count
        if delimiter_scores:
            # Sort by consistency first, then by column count
            best_delimiter = max(delimiter_scores.items(), 
                               key=lambda x: (x[1]['consistency'], x[1]['columns']))
            delimiter = best_delimiter[0]
            
            print(f"Detected delimiter: '{delimiter}' with {best_delimiter[1]['columns']} columns "
                  f"(consistency: {best_delimiter[1]['consistency']:.2f})")
        else:
            # Fallback: try to detect by analyzing the first line
            if lines:
                first_line = lines[0]
                # Look for patterns that suggest space-separated values
                if len(first_line.split()) > 1:
                    delimiter = ' '  # Space-separated
                    print(f"Fallback: Using space delimiter")
                else:
                    delimiter = '\t'  # Default to tab
                    print(f"Fallback: Using tab delimiter")
            else:
                delimiter = '\t'
                print(f"Fallback: Using tab delimiter (no lines found)")
        
        return encoding, delimiter
        
    except Exception as e:
        print(f"Error in delimiter detection: {e}")
        return 'utf-8', '\t'

def parse_trial_balance(file_path: str) -> tuple[pd.DataFrame, str, str]:
    """Parse the ASCII trial balance file with improved delimiter handling"""
    encoding, delimiter = detect_encoding_and_delimiter(file_path)
    
    try:
        # Read the file with the detected delimiter
        if delimiter == ' ' or delimiter == '  ':
            # For space delimiters, use a more robust approach
            df = pd.read_csv(file_path, sep=r'\s+', encoding=encoding, header=None, engine='python')
        else:
            # For other delimiters, use standard pandas parsing
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, header=None)
        
        # Clean up the data
        df = df.dropna(how='all')  # Remove completely empty rows
        
        print(f"Parsed file with {len(df.columns)} columns: {list(df.columns)}")
        print(f"First few rows:\n{df.head()}")
        
        # Check if we have the expected columns (account code + amounts)
        if len(df.columns) >= 2:
            # Standardize column names based on TEA trial balance format
            if len(df.columns) == 4:
                df.columns = ['account_code', 'current_year_actual', 'budget', 'prior_year_actual']
            elif len(df.columns) == 3:
                df.columns = ['account_code', 'current_year_actual', 'budget']
            elif len(df.columns) == 2:
                df.columns = ['account_code', 'current_year_actual']
            else:
                df.columns = ['account_code'] + [f'amount_{i}' for i in range(1, len(df.columns))]
            
            # Clean account codes
            df['account_code'] = df['account_code'].astype(str).str.strip()
            
            # Convert amounts to numeric, handling any non-numeric values
            for col in df.columns[1:]:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            print(f"Final parsed data shape: {df.shape}")
            print(f"Column names: {list(df.columns)}")
            
            return df, encoding, delimiter
        else:
            raise ValueError(f"File must have at least 2 columns, but found {len(df.columns)} columns")
            
    except Exception as e:
        print(f"Error parsing file: {str(e)}")
        raise ValueError(f"Error parsing file: {str(e)}")

@app.get("/")
async def root():
    """API root endpoint"""
    return {"message": "TEA Financial Statement Generator API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload and parse trial balance file"""
    
    # Validate file
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")
    
    # Save file
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    try:
        # Parse the trial balance
        df, encoding, delimiter = parse_trial_balance(file_path)
        
        # Store in database
        user_id = current_user["id"]
        save_trial_balance_data(
            user_id=user_id,
            filename=file.filename,
            encoding=encoding,
            delimiter=delimiter,
            rows=len(df),
            columns=len(df.columns),
            data_json=df.to_json()
        )
        
        return JSONResponse({
            "success": True,
            "message": f"File uploaded successfully. Found {len(df)} rows.",
            "file_info": {
                'filename': file.filename,
                'encoding': encoding,
                'delimiter': delimiter,
                'rows': len(df),
                'columns': len(df.columns)
            }
        })
        
    except Exception as e:
        # Clean up file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/data")
async def get_data(
    current_user: dict = Depends(get_current_user)
):
    """Get uploaded trial balance data"""
    user_id = current_user["id"]
    
    # Get data from database
    data = get_trial_balance_data(user_id)
    if not data:
        raise HTTPException(status_code=400, detail="No data uploaded")
    
    df = pd.read_json(data['data_json'])
    return JSONResponse({
        "data": df.values.tolist(),  # Convert to array of arrays format
        "file_info": {
            'filename': data['filename'],
            'encoding': data['encoding'],
            'delimiter': data['delimiter'],
            'rows': data['rows'],
            'columns': data['columns']
        }
    })

@app.get("/api/mapping")
async def get_mapping(
    page: int = 1,
    page_size: int = 100,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get account mapping configuration with pagination"""
    user_id = current_user["id"]
    
    # Get mappings from database
    result = get_account_mappings(user_id, page, page_size, search)
    
    # Return empty result if no mappings exist - don't auto-create
    return JSONResponse(result)

@app.post("/api/mapping/auto-map")
async def auto_map_accounts(
    current_user: dict = Depends(get_current_user)
):
    """Create default mapping from uploaded trial balance data"""
    user_id = current_user["id"]
    
    # Get trial balance data
    data = get_trial_balance_data(user_id)
    if not data:
        raise HTTPException(status_code=400, detail="No trial balance data found. Please upload a file first.")
    
    # Create default mapping from trial balance data
    df = pd.read_json(data['data_json'])
    account_codes = df['account_code'].unique().tolist()
    default_mapping = create_default_mapping(account_codes)
    
    # Save default mappings to database
    save_account_mappings(user_id, default_mapping)
    
    # Get the saved mappings with pagination
    result = get_account_mappings(user_id, page=1, page_size=100)
    
    return JSONResponse({
        "success": True,
        "message": f"Auto-mapped {len(account_codes)} accounts successfully",
        "mappings": result['mappings'],
        "pagination": result['pagination']
    })

@app.post("/api/mapping")
async def save_mapping(
    mapping: Dict[str, Any],
    current_user: dict = Depends(get_current_user)
):
    """Save account mapping configuration"""
    user_id = current_user["id"]
    
    # Save mappings to database
    save_account_mappings(user_id, mapping)
    
    # Get all mappings for validation
    all_mappings_result = get_account_mappings(user_id, page=1, page_size=10000)  # Get all
    all_mappings = all_mappings_result['mappings']
    
    # Validate the complete mapping
    validation_result = validate_mapping(all_mappings)
    
    return JSONResponse({
        "success": True, 
        "message": "Mapping saved successfully",
        "validation": validation_result
    })

@app.delete("/api/mapping")
async def delete_all_mappings(
    current_user: dict = Depends(get_current_user)
):
    """Delete all account mappings for the current user"""
    user_id = current_user["id"]
    
    # Delete all mappings from database
    save_account_mappings(user_id, {})  # Empty dict deletes all
    
    # Also clear audit trail data since it depends on mappings
    clear_audit_trail(user_id)
    
    return JSONResponse({
        "success": True, 
        "message": "All mappings and audit trail data deleted successfully"
    })

@app.post("/api/generate-statements")
async def generate_statements(
    current_user: dict = Depends(get_current_user)
):
    """Generate financial statements"""
    user_id = current_user["id"]
    
    # Get trial balance data from database
    data = get_trial_balance_data(user_id)
    if not data:
        raise HTTPException(status_code=400, detail="No data uploaded")
    
    # Get trial balance data
    df = pd.read_json(data['data_json'])
    
    # Get account mappings from database
    mappings_result = get_account_mappings(user_id, page=1, page_size=10000)  # Get all mappings
    mappings = mappings_result['mappings']
    
    if not mappings:
        raise HTTPException(status_code=400, detail="No account mappings found. Please create mappings first.")
    
    # Apply mapping and generate statements
    # This is a simplified version - in production, implement full statement generation
    statements = {
        "government_wide_net_position": generate_government_wide_net_position(df, mappings),
        "government_wide_activities": generate_government_wide_activities(df, mappings),
        "governmental_funds_balance": generate_governmental_funds_balance(df, mappings),
        "governmental_funds_revenues_expenditures": generate_governmental_funds_revenues_expenditures(df, mappings)
    }
    
    # Store statements in database
    save_financial_statements(user_id, "combined", statements)
    
    return JSONResponse({
        "success": True,
        "statements": statements
    })

def generate_government_wide_net_position(df: pd.DataFrame, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Statement of Net Position in the exact format provided by the user.
    Structure matches the provided example with specific line items and account codes.
    """
    
    # Initialize detailed statement structure matching the provided format
    statement = {
        "title": "STATEMENT OF NET POSITION",
        # "subtitle": "Data Control Codes\t\tGovernmental Activities",
        "assets": {
            "cash_and_cash_equivalents": {"code": "1110", "description": "Cash and Cash Equivalents", "amount": 0},
            "property_taxes_receivable": {"code": "1225", "description": "Property Taxes Receivable (Net)", "amount": 0},
            "due_from_other_governments": {"code": "1240", "description": "Due from Other Governments", "amount": 0},
            "due_from_fiduciary": {"code": "1267", "description": "Due from Fiduciary", "amount": 0},
            "other_receivables": {"code": "1290", "description": "Other Receivables (Net)", "amount": 0},
            "inventories": {"code": "1300", "description": "Inventories", "amount": 0},
            "unrealized_expenses": {"code": "1410", "description": "Unrealized Expenses", "amount": 0},
            "capital_assets": {
                "land": {"code": "1510", "description": "Land", "amount": 0},
                "buildings_improvements": {"code": "1520", "description": "Buildings and Improvements, Net", "amount": 0},
                "furniture_equipment": {"code": "1530", "description": "Furniture and Equipment, Net", "amount": 0},
                "construction_in_progress": {"code": "1580", "description": "Construction in Progress", "amount": 0}
            },
            "total_assets": {"code": "1000", "description": "Total Assets", "amount": 0}
        },
        "deferred_outflows": {
            "deferred_charge_refunding": {"code": "1701", "description": "Deferred Charge for Refunding", "amount": 0},
            "deferred_outflow_pensions": {"code": "1705", "description": "Deferred Outflow Related to Pensions", "amount": 0},
            "deferred_outflow_opeb": {"code": "1706", "description": "Deferred Outflow Related to OPEB", "amount": 0},
            "total_deferred_outflows": {"code": "1700", "description": "Total Deferred Outflows of Resources", "amount": 0}
        },
        "liabilities": {
            "accounts_payable": {"code": "2110", "description": "Accounts Payable", "amount": 0},
            "interest_payable": {"code": "2140", "description": "Interest Payable", "amount": 0},
            "accrued_liabilities": {"code": "2165", "description": "Accrued Liabilities", "amount": 0},
            "due_to_other_governments": {"code": "2180", "description": "Due to Other Governments", "amount": 0},
            "unearned_revenue": {"code": "2300", "description": "Unearned Revenue", "amount": 0},
            "noncurrent_liabilities": {
                "due_within_one_year": {"code": "2501", "description": "Due Within One Year", "amount": 0},
                "due_more_than_one_year": {"code": "2502", "description": "Due in More Than One Year", "amount": 0},
                "net_pension_liability": {"code": "2540", "description": "Net Pension Liability", "amount": 0},
                "net_opeb_liability": {"code": "2545", "description": "Net OPEB Liability", "amount": 0}
            },
            "total_liabilities": {"code": "2000", "description": "Total Liabilities", "amount": 0}
        },
        "deferred_inflows": {
            "deferred_inflow_pensions": {"code": "2605", "description": "Deferred Inflow Related to Pensions", "amount": 0},
            "deferred_inflow_opeb": {"code": "2606", "description": "Deferred Inflow Related to OPEB", "amount": 0},
            "total_deferred_inflows": {"code": "2600", "description": "Total Deferred Inflows of Resources", "amount": 0}
        },
        "net_position": {
            "net_investment_capital_assets": {"code": "3200", "description": "Net Investment in Capital Assets", "amount": 0},
            "restricted": {
                "state_federal_programs": {"code": "3820", "description": "State and Federal Programs", "amount": 0},
                "debt_service": {"code": "3850", "description": "Debt Service", "amount": 0}
            },
            "unrestricted": {"code": "3900", "description": "Unrestricted", "amount": 0},
            "total_net_position": {"code": "3000", "description": "Total Net Position", "amount": 0}
        },
        "balance_validation": {
            "left_side": 0,  # Assets + Deferred Outflows
            "right_side": 0,  # Liabilities + Deferred Inflows + Net Position
            "balanced": False
        }
    }
    
    # Process each account in the trial balance
    for _, row in df.iterrows():
        account_code = str(row['account_code'])
        amount = row.get('current_year_actual', 0)
        
        if account_code in mapping:
            account_mapping = mapping[account_code]
            gasb_category = account_mapping.get('gasb_category', '')
            tea_category = account_mapping.get('tea_category', '')
            
            # Extract object code from positions 5-8 (TEA standard)
            object_code = account_code[5:9] if len(account_code) >= 9 else '0000'
            
            # Map accounts to specific line items using pattern matching for comprehensive coverage
            if object_code.startswith('1'):  # All assets (1000-1999)
                if object_code.startswith('11'):  # Cash and equivalents (1100-1199)
                    statement['assets']['cash_and_cash_equivalents']['amount'] += amount
                elif object_code.startswith('12'):  # Receivables (1200-1299)
                    if object_code == '1225':
                        statement['assets']['property_taxes_receivable']['amount'] += amount
                    elif object_code == '1240':
                        statement['assets']['due_from_other_governments']['amount'] += amount
                    elif object_code == '1267':
                        statement['assets']['due_from_fiduciary']['amount'] += amount
                    else:
                        statement['assets']['other_receivables']['amount'] += amount
                elif object_code.startswith('13'):  # Inventories (1300-1399)
                    statement['assets']['inventories']['amount'] += amount
                elif object_code.startswith('14'):  # Prepaid/Other current assets (1400-1499)
                    statement['assets']['unrealized_expenses']['amount'] += amount
                elif object_code.startswith('15'):  # Capital assets (1500-1599)
                    if object_code == '1510':
                        statement['assets']['capital_assets']['land']['amount'] += amount
                    elif object_code == '1520':
                        statement['assets']['capital_assets']['buildings_improvements']['amount'] += amount
                    elif object_code == '1530':
                        statement['assets']['capital_assets']['furniture_equipment']['amount'] += amount
                    elif object_code == '1580':
                        statement['assets']['capital_assets']['construction_in_progress']['amount'] += amount
                    else:
                        # Default to buildings and improvements for unmapped capital assets
                        statement['assets']['capital_assets']['buildings_improvements']['amount'] += amount
                elif object_code.startswith('17'):  # Deferred outflows (1700-1799)
                    if object_code == '1701':
                        statement['deferred_outflows']['deferred_charge_refunding']['amount'] += amount
                    elif object_code == '1705':
                        statement['deferred_outflows']['deferred_outflow_pensions']['amount'] += amount
                    elif object_code == '1706':
                        statement['deferred_outflows']['deferred_outflow_opeb']['amount'] += amount
                    else:
                        # Default to deferred charge for refunding
                        statement['deferred_outflows']['deferred_charge_refunding']['amount'] += amount
                        
            elif object_code.startswith('2'):  # All liabilities (2000-2999)
                if object_code.startswith('21'):  # Current liabilities (2100-2199)
                    if object_code == '2110':
                        statement['liabilities']['accounts_payable']['amount'] += amount
                    elif object_code == '2140':
                        statement['liabilities']['interest_payable']['amount'] += amount
                    elif object_code == '2165':
                        statement['liabilities']['accrued_liabilities']['amount'] += amount
                    elif object_code == '2180':
                        statement['liabilities']['due_to_other_governments']['amount'] += amount
                    elif object_code == '2300':
                        statement['liabilities']['unearned_revenue']['amount'] += amount
                    else:
                        # Default to accounts payable for unmapped current liabilities
                        statement['liabilities']['accounts_payable']['amount'] += amount
                elif object_code.startswith('25'):  # Long-term liabilities (2500-2599)
                    if object_code == '2501':
                        statement['liabilities']['noncurrent_liabilities']['due_within_one_year']['amount'] += amount
                    elif object_code == '2502':
                        statement['liabilities']['noncurrent_liabilities']['due_more_than_one_year']['amount'] += amount
                    elif object_code == '2540':
                        statement['liabilities']['noncurrent_liabilities']['net_pension_liability']['amount'] += amount
                    elif object_code == '2545':
                        statement['liabilities']['noncurrent_liabilities']['net_opeb_liability']['amount'] += amount
                    else:
                        # Default to due in more than one year for unmapped long-term liabilities
                        statement['liabilities']['noncurrent_liabilities']['due_more_than_one_year']['amount'] += amount
                elif object_code.startswith('26'):  # Deferred inflows (2600-2699)
                    if object_code == '2605':
                        statement['deferred_inflows']['deferred_inflow_pensions']['amount'] += amount
                    elif object_code == '2606':
                        statement['deferred_inflows']['deferred_inflow_opeb']['amount'] += amount
                    else:
                        # Default to deferred inflow related to pensions
                        statement['deferred_inflows']['deferred_inflow_pensions']['amount'] += amount
                        
            elif object_code.startswith('3'):  # All net position (3000-3999)
                if object_code.startswith('32'):  # Net investment in capital assets (3200-3299)
                    statement['net_position']['net_investment_capital_assets']['amount'] += amount
                elif object_code.startswith('38'):  # Restricted net position (3800-3899)
                    if object_code == '3820':
                        statement['net_position']['restricted']['state_federal_programs']['amount'] += amount
                    elif object_code == '3850':
                        statement['net_position']['restricted']['debt_service']['amount'] += amount
                    else:
                        # Default to state and federal programs for unmapped restricted net position
                        statement['net_position']['restricted']['state_federal_programs']['amount'] += amount
                elif object_code.startswith('39'):  # Unrestricted net position (3900-3999)
                    statement['net_position']['unrestricted']['amount'] += amount
    
    # Calculate totals
    # Total Assets
    statement['assets']['total_assets']['amount'] = (
        statement['assets']['cash_and_cash_equivalents']['amount'] +
        statement['assets']['property_taxes_receivable']['amount'] +
        statement['assets']['due_from_other_governments']['amount'] +
        statement['assets']['due_from_fiduciary']['amount'] +
        statement['assets']['other_receivables']['amount'] +
        statement['assets']['inventories']['amount'] +
        statement['assets']['unrealized_expenses']['amount'] +
        statement['assets']['capital_assets']['land']['amount'] +
        statement['assets']['capital_assets']['buildings_improvements']['amount'] +
        statement['assets']['capital_assets']['furniture_equipment']['amount'] +
        statement['assets']['capital_assets']['construction_in_progress']['amount']
    )
    
    # Total Deferred Outflows
    statement['deferred_outflows']['total_deferred_outflows']['amount'] = (
        statement['deferred_outflows']['deferred_charge_refunding']['amount'] +
        statement['deferred_outflows']['deferred_outflow_pensions']['amount'] +
        statement['deferred_outflows']['deferred_outflow_opeb']['amount']
    )
    
    # Total Liabilities
    statement['liabilities']['total_liabilities']['amount'] = (
        statement['liabilities']['accounts_payable']['amount'] +
        statement['liabilities']['interest_payable']['amount'] +
        statement['liabilities']['accrued_liabilities']['amount'] +
        statement['liabilities']['due_to_other_governments']['amount'] +
        statement['liabilities']['unearned_revenue']['amount'] +
        statement['liabilities']['noncurrent_liabilities']['due_within_one_year']['amount'] +
        statement['liabilities']['noncurrent_liabilities']['due_more_than_one_year']['amount'] +
        statement['liabilities']['noncurrent_liabilities']['net_pension_liability']['amount'] +
        statement['liabilities']['noncurrent_liabilities']['net_opeb_liability']['amount']
    )
    
    # Total Deferred Inflows
    statement['deferred_inflows']['total_deferred_inflows']['amount'] = (
        statement['deferred_inflows']['deferred_inflow_pensions']['amount'] +
        statement['deferred_inflows']['deferred_inflow_opeb']['amount']
    )
    
    # Total Net Position
    statement['net_position']['total_net_position']['amount'] = (
        statement['net_position']['net_investment_capital_assets']['amount'] +
        statement['net_position']['restricted']['state_federal_programs']['amount'] +
        statement['net_position']['restricted']['debt_service']['amount'] +
        statement['net_position']['unrestricted']['amount']
    )
    
    # Balance validation: (Assets + Deferred Outflows) = (Liabilities + Deferred Inflows + Net Position)
    statement['balance_validation']['left_side'] = (
        statement['assets']['total_assets']['amount'] +
        statement['deferred_outflows']['total_deferred_outflows']['amount']
    )
    
    statement['balance_validation']['right_side'] = (
        statement['liabilities']['total_liabilities']['amount'] +
        statement['deferred_inflows']['total_deferred_inflows']['amount'] +
        statement['net_position']['total_net_position']['amount']
    )
    
    statement['balance_validation']['balanced'] = abs(
        statement['balance_validation']['left_side'] - 
        statement['balance_validation']['right_side']
    ) < 0.01  # Allow for small rounding differences
    
    return statement

def generate_government_wide_activities(df: pd.DataFrame, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Statement of Activities in the exact format provided by the user.
    Structure matches the provided example with specific program functions and general revenues.
    """
    
    # Initialize detailed statement structure matching the provided format
    statement = {
        "title": "STATEMENT OF ACTIVITIES",
        "governmental_activities": {
            "instruction": {"code": "11", "description": "Instruction", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "instructional_resources": {"code": "12", "description": "Instructional Resources and Media Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "curriculum_staff_dev": {"code": "13", "description": "Curriculum and Staff Development", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "instructional_leadership": {"code": "21", "description": "Instructional Leadership", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "school_leadership": {"code": "23", "description": "School Leadership", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "guidance_counseling": {"code": "31", "description": "Guidance, Counseling, and Evaluation Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "social_work": {"code": "32", "description": "Social Work Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "health_services": {"code": "33", "description": "Health Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "student_transportation": {"code": "34", "description": "Student Transportation", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "food_service": {"code": "35", "description": "Food Service", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "cocurricular": {"code": "36", "description": "Cocurricular/Extracurricular Activities", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "general_admin": {"code": "41", "description": "General Administration", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "facilities_maintenance": {"code": "51", "description": "Facilities Maintenance and Operations", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "security_monitoring": {"code": "52", "description": "Security and Monitoring Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "data_processing": {"code": "53", "description": "Data Processing Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "community_services": {"code": "61", "description": "Community Services", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "interest_long_term_debt": {"code": "72", "description": "Interest on Long-term Debt", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "bond_issuance_costs": {"code": "73", "description": "Bond Issuance Costs and Fees", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "capital_outlay": {"code": "81", "description": "Capital Outlay", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "shared_services": {"code": "93", "description": "Payments Related to Shared Services Arrangements", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "other_intergovernmental": {"code": "99", "description": "Other Intergovernmental Charges", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "total_governmental": {"code": "TG", "description": "Total Governmental Activities", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0},
            "total_primary": {"code": "TP", "description": "Total Primary Government", "expenses": 0, "charges_for_services": 0, "operating_grants": 0, "net_expense_revenue": 0}
        },
        "general_revenues": {
            "property_taxes_general": {"code": "MT", "description": "Property Taxes, Levied for General Purposes", "amount": 0},
            "property_taxes_debt": {"code": "DT", "description": "Property Taxes, Levied for Debt Service", "amount": 0},
            "chapter_313_payments": {"code": "", "description": "Chapter 313 Payments", "amount": 0},
            "investment_earnings": {"code": "IE", "description": "Investment Earnings", "amount": 0},
            "grants_contributions": {"code": "GC", "description": "Grants and Contributions Not Restricted to Specific Programs", "amount": 0},
            "miscellaneous": {"code": "MI", "description": "Miscellaneous", "amount": 0},
            "total_general_revenues": {"code": "TR", "description": "Total General Revenues and Transfers", "amount": 0}
        },
        "net_position": {
            "change_in_net_position": {"code": "CN", "description": "Change in Net Position", "amount": 0},
            "net_position_beginning": {"code": "NB", "description": "Net Position - Beginning", "amount": 0},
            "net_position_ending": {"code": "NE", "description": "Net Position - Ending", "amount": 0}
        }
    }
    
    # Process each account in the trial balance
    for _, row in df.iterrows():
        account_code = str(row['account_code'])
        amount = row.get('current_year_actual', 0)
        
        if account_code in mapping:
            account_mapping = mapping[account_code]
            gasb_category = account_mapping.get('gasb_category', '')
            tea_category = account_mapping.get('tea_category', '')
            
            # Map accounts to specific program functions based on account codes and categories
            if gasb_category == 'program_expenses' or gasb_category == 'general_expenses':
                # Extract function code from positions 3-4 (TEA standard)
                function_code = account_code[3:5] if len(account_code) >= 5 else '00'
                
                # Map to specific program functions based on function codes
                if function_code == '11':  # Instruction
                    statement['governmental_activities']['instruction']['expenses'] += amount
                elif function_code == '12':  # Instructional Resources
                    statement['governmental_activities']['instructional_resources']['expenses'] += amount
                elif function_code == '13':  # Curriculum and Staff Development
                    statement['governmental_activities']['curriculum_staff_dev']['expenses'] += amount
                elif function_code == '21':  # Instructional Leadership
                    statement['governmental_activities']['instructional_leadership']['expenses'] += amount
                elif function_code == '23':  # School Leadership
                    statement['governmental_activities']['school_leadership']['expenses'] += amount
                elif function_code == '31':  # Guidance, Counseling
                    statement['governmental_activities']['guidance_counseling']['expenses'] += amount
                elif function_code == '32':  # Social Work Services
                    statement['governmental_activities']['social_work']['expenses'] += amount
                elif function_code == '33':  # Health Services
                    statement['governmental_activities']['health_services']['expenses'] += amount
                elif function_code == '34':  # Student Transportation
                    statement['governmental_activities']['student_transportation']['expenses'] += amount
                elif function_code == '35':  # Food Service
                    statement['governmental_activities']['food_service']['expenses'] += amount
                elif function_code == '36':  # Cocurricular/Extracurricular
                    statement['governmental_activities']['cocurricular']['expenses'] += amount
                elif function_code == '41':  # General Administration
                    statement['governmental_activities']['general_admin']['expenses'] += amount
                elif function_code == '51':  # Facilities Maintenance
                    statement['governmental_activities']['facilities_maintenance']['expenses'] += amount
                elif function_code == '52':  # Security and Monitoring
                    statement['governmental_activities']['security_monitoring']['expenses'] += amount
                elif function_code == '53':  # Data Processing
                    statement['governmental_activities']['data_processing']['expenses'] += amount
                elif function_code == '61':  # Community Services
                    statement['governmental_activities']['community_services']['expenses'] += amount
                elif function_code == '72':  # Interest on Long-term Debt
                    statement['governmental_activities']['interest_long_term_debt']['expenses'] += amount
                elif function_code == '73':  # Bond Issuance Costs
                    statement['governmental_activities']['bond_issuance_costs']['expenses'] += amount
                elif function_code == '81':  # Capital Outlay
                    statement['governmental_activities']['capital_outlay']['expenses'] += amount
                elif function_code == '93':  # Shared Services
                    statement['governmental_activities']['shared_services']['expenses'] += amount
                elif function_code == '99':  # Other Intergovernmental
                    statement['governmental_activities']['other_intergovernmental']['expenses'] += amount
                else:
                    # Default to General Administration for unmapped expenses
                    statement['governmental_activities']['general_admin']['expenses'] += amount
                    
            elif gasb_category == 'program_revenues':
                # Extract function code from positions 3-4 (TEA standard)
                function_code = account_code[3:5] if len(account_code) >= 5 else '00'
                
                # Map program revenues to appropriate programs
                if function_code == '36':  # Cocurricular/Extracurricular (charges for services)
                    statement['governmental_activities']['cocurricular']['charges_for_services'] += amount
                elif function_code == '11':  # Instruction (operating grants)
                    statement['governmental_activities']['instruction']['operating_grants'] += amount
                else:
                    # Default to operating grants for most program revenues
                    statement['governmental_activities']['instruction']['operating_grants'] += amount
                    
            elif gasb_category == 'general_revenues':
                # Map general revenues to appropriate categories
                if 'MT' in account_code or 'property' in tea_category.lower():
                    statement['general_revenues']['property_taxes_general']['amount'] += amount
                elif 'DT' in account_code or 'debt' in tea_category.lower():
                    statement['general_revenues']['property_taxes_debt']['amount'] += amount
                elif '313' in account_code or 'chapter' in tea_category.lower():
                    statement['general_revenues']['chapter_313_payments']['amount'] += amount
                elif 'IE' in account_code or 'investment' in tea_category.lower():
                    statement['general_revenues']['investment_earnings']['amount'] += amount
                elif 'GC' in account_code or 'grant' in tea_category.lower():
                    statement['general_revenues']['grants_contributions']['amount'] += amount
                elif 'MI' in account_code or 'miscellaneous' in tea_category.lower():
                    statement['general_revenues']['miscellaneous']['amount'] += amount
                else:
                    # Default to miscellaneous for unmapped general revenues
                    statement['general_revenues']['miscellaneous']['amount'] += amount
    
    # Calculate net expense/revenue for each program
    for program_key, program_data in statement['governmental_activities'].items():
        if program_key not in ['total_governmental', 'total_primary']:
            program_data['net_expense_revenue'] = (
                program_data['expenses'] - 
                program_data['charges_for_services'] - 
                program_data['operating_grants']
            )
    
    # Calculate totals for governmental activities
    total_expenses = sum(program['expenses'] for key, program in statement['governmental_activities'].items() 
                        if key not in ['total_governmental', 'total_primary'])
    total_charges = sum(program['charges_for_services'] for key, program in statement['governmental_activities'].items() 
                       if key not in ['total_governmental', 'total_primary'])
    total_grants = sum(program['operating_grants'] for key, program in statement['governmental_activities'].items() 
                      if key not in ['total_governmental', 'total_primary'])
    total_net_expense = sum(program['net_expense_revenue'] for key, program in statement['governmental_activities'].items() 
                           if key not in ['total_governmental', 'total_primary'])
    
    statement['governmental_activities']['total_governmental']['expenses'] = total_expenses
    statement['governmental_activities']['total_governmental']['charges_for_services'] = total_charges
    statement['governmental_activities']['total_governmental']['operating_grants'] = total_grants
    statement['governmental_activities']['total_governmental']['net_expense_revenue'] = total_net_expense
    
    statement['governmental_activities']['total_primary']['expenses'] = total_expenses
    statement['governmental_activities']['total_primary']['charges_for_services'] = total_charges
    statement['governmental_activities']['total_primary']['operating_grants'] = total_grants
    statement['governmental_activities']['total_primary']['net_expense_revenue'] = total_net_expense
    
    # Calculate total general revenues
    total_general_revenues = sum(revenue['amount'] for revenue in statement['general_revenues'].values() 
                               if revenue['code'] != 'TR')
    statement['general_revenues']['total_general_revenues']['amount'] = total_general_revenues
    
    # Calculate change in net position
    change_in_net_position = total_general_revenues + total_net_expense
    statement['net_position']['change_in_net_position']['amount'] = change_in_net_position
    
    # Set beginning net position (this would typically come from previous year data)
    # For now, we'll calculate it based on ending net position from Statement of Net Position
    statement['net_position']['net_position_beginning']['amount'] = 37913236  # Example value
    
    # Calculate ending net position
    ending_net_position = statement['net_position']['net_position_beginning']['amount'] + change_in_net_position
    statement['net_position']['net_position_ending']['amount'] = ending_net_position
    
    return statement

def generate_governmental_funds_balance(df: pd.DataFrame, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Balance Sheet - Governmental Funds in the exact format provided by the user.
    Structure shows financial position by fund type (General Fund, Debt Service Fund, etc.).
    """
    
    # Initialize detailed statement structure matching the provided format
    statement = {
        "title": "BALANCE SHEET - GOVERNMENTAL FUNDS",
        "funds": {
            "general_fund": "General Fund",
            "non_major_funds": "Non-Major Funds"
        },
        "assets": {
            "cash_and_equivalents": {"code": "1110", "description": "Cash and Cash Equivalents", "general_fund": 0, "non_major_funds": 0},
            "taxes_receivable": {"code": "1225", "description": "Taxes Receivable, Net", "general_fund": 0, "non_major_funds": 0},
            "due_from_other_governments": {"code": "1240", "description": "Due from Other Governments", "general_fund": 0, "non_major_funds": 0},
            "due_from_other_funds": {"code": "1260", "description": "Due from Other Funds", "general_fund": 0, "non_major_funds": 0},
            "other_receivables": {"code": "1290", "description": "Other Receivables", "general_fund": 0, "non_major_funds": 0},
            "inventories": {"code": "1300", "description": "Inventories", "general_fund": 0, "non_major_funds": 0},
            "unrealized_expenditures": {"code": "1410", "description": "Unrealized Expenditures", "general_fund": 0, "non_major_funds": 0},
            "total_assets": {"code": "1000", "description": "Total Assets", "general_fund": 0, "non_major_funds": 0}
        },
        "liabilities": {
            "current_liabilities": {
                "accounts_payable": {"code": "2110", "description": "Accounts Payable", "general_fund": 0, "non_major_funds": 0},
                "payroll_deductions": {"code": "2150", "description": "Payroll Deductions and Withholdings", "general_fund": 0, "non_major_funds": 0},
                "accrued_wages": {"code": "2160", "description": "Accrued Wages Payable", "general_fund": 0, "non_major_funds": 0},
                "due_to_other_funds": {"code": "2170", "description": "Due to Other Funds", "general_fund": 0, "non_major_funds": 0},
                "due_to_other_governments": {"code": "2180", "description": "Due to Other Governments", "general_fund": 0, "non_major_funds": 0},
                "unearned_revenue": {"code": "2300", "description": "Unearned Revenue", "general_fund": 0, "non_major_funds": 0}
            },
            "total_liabilities": {"code": "2000", "description": "Total Liabilities", "general_fund": 0, "non_major_funds": 0}
        },
        "deferred_inflows": {
            "unavailable_revenue_property_taxes": {"code": "2601", "description": "Unavailable Revenue - Property Taxes", "general_fund": 0, "non_major_funds": 0},
            "total_deferred_inflows": {"code": "2600", "description": "Total Deferred Inflows of Resources", "general_fund": 0, "non_major_funds": 0}
        },
        "fund_balances": {
            "nonspendable": {
                "inventories": {"code": "3410", "description": "Inventories", "general_fund": 0, "non_major_funds": 0},
                "prepaid_items": {"code": "3430", "description": "Prepaid Items", "general_fund": 0, "non_major_funds": 0}
            },
            "restricted": {
                "federal_state_funds": {"code": "3450", "description": "Federal/State Funds Grant Restrictions", "general_fund": 0, "non_major_funds": 0},
                "retirement_long_term_debt": {"code": "3480", "description": "Retirement of Long-Term Debt", "general_fund": 0, "non_major_funds": 0},
                "other_restrictions": {"code": "3490", "description": "Other Restrictions of Fund Balance", "general_fund": 0, "non_major_funds": 0}
            },
            "committed": {
                "construction": {"code": "3510", "description": "Construction", "general_fund": 0, "non_major_funds": 0},
                "other_committed": {"code": "3545", "description": "Other Committed Fund Balance", "general_fund": 0, "non_major_funds": 0}
            },
            "assigned": {
                "other_assigned": {"code": "3590", "description": "Other Assigned Fund Balance", "general_fund": 0, "non_major_funds": 0}
            },
            "unassigned": {"code": "3600", "description": "Unassigned", "general_fund": 0, "non_major_funds": 0},
            "total_fund_balances": {"code": "3000", "description": "Total Fund Balances", "general_fund": 0, "non_major_funds": 0}
        },
        "total_liabilities_deferred_fund_balances": {"code": "4000", "description": "Total Liabilities, Deferred Inflow of Resources and Fund Balances", "general_fund": 0, "non_major_funds": 0}
    }
    
    # Vectorized aggregation
    if df.empty:
        return statement

    dfv = df.copy()
    dfv['account_code'] = dfv['account_code'].astype(str)
    dfv['object_code'] = dfv['account_code'].str.slice(5, 9)
    dfv['function_code'] = dfv['account_code'].str.slice(3, 5)
    dfv['amount'] = pd.to_numeric(dfv.get('current_year_actual', 0), errors='coerce').fillna(0)

    # Build mapping DataFrame
    map_df = pd.DataFrame.from_dict(mapping, orient='index') if mapping else pd.DataFrame()
    if not map_df.empty and 'account_code' not in map_df.columns:
        map_df['account_code'] = map_df.index
    if not map_df.empty:
        dfv = dfv.merge(map_df[['account_code', 'fund_category']], on='account_code', how='left')
    else:
        dfv['fund_category'] = 'general_fund'
    dfv['fund_key'] = dfv['fund_category'].apply(lambda x: 'general_fund' if x == 'general_fund' else 'non_major_funds')

    def add_sum(mask, target_path):
        sums = dfv[mask].groupby('fund_key')['amount'].sum()
        for fk, val in sums.items():
            # Navigate nested dict
            node = statement
            for key in target_path[:-1]:
                node = node[key]
            node[target_path[-1]][fk] += float(val)

    # Assets
    add_sum(dfv['object_code'].str.startswith('11'), ['assets', 'cash_and_equivalents'])
    add_sum(dfv['object_code'].eq('1225'), ['assets', 'taxes_receivable'])
    add_sum(dfv['object_code'].eq('1240'), ['assets', 'due_from_other_governments'])
    add_sum(dfv['object_code'].eq('1260'), ['assets', 'due_from_other_funds'])
    add_sum(dfv['object_code'].str.startswith('12') & ~dfv['object_code'].isin(['1225', '1240', '1260']), ['assets', 'other_receivables'])
    add_sum(dfv['object_code'].str.startswith('13'), ['assets', 'inventories'])
    add_sum(dfv['object_code'].str.startswith('14'), ['assets', 'unrealized_expenditures'])

    # Liabilities
    add_sum(dfv['object_code'].eq('2110'), ['liabilities', 'current_liabilities', 'accounts_payable'])
    add_sum(dfv['object_code'].eq('2150'), ['liabilities', 'current_liabilities', 'payroll_deductions'])
    add_sum(dfv['object_code'].eq('2160'), ['liabilities', 'current_liabilities', 'accrued_wages'])
    add_sum(dfv['object_code'].eq('2170'), ['liabilities', 'current_liabilities', 'due_to_other_funds'])
    add_sum(dfv['object_code'].eq('2180'), ['liabilities', 'current_liabilities', 'due_to_other_governments'])
    add_sum(dfv['object_code'].eq('2300'), ['liabilities', 'current_liabilities', 'unearned_revenue'])

    # Deferred inflows
    add_sum(dfv['object_code'].eq('2601') | dfv['object_code'].str.startswith('26'), ['deferred_inflows', 'unavailable_revenue_property_taxes'])

    # Fund balances
    add_sum(dfv['object_code'].eq('3410'), ['fund_balances', 'nonspendable', 'inventories'])
    add_sum(dfv['object_code'].eq('3430'), ['fund_balances', 'nonspendable', 'prepaid_items'])
    add_sum(dfv['object_code'].eq('3450'), ['fund_balances', 'restricted', 'federal_state_funds'])
    add_sum(dfv['object_code'].eq('3480'), ['fund_balances', 'restricted', 'retirement_long_term_debt'])
    add_sum(dfv['object_code'].eq('3490') | (dfv['object_code'].str.startswith('34') & ~dfv['object_code'].isin(['3410', '3430', '3450', '3480'])), ['fund_balances', 'restricted', 'other_restrictions'])
    add_sum(dfv['object_code'].eq('3510'), ['fund_balances', 'committed', 'construction'])
    add_sum(dfv['object_code'].eq('3545'), ['fund_balances', 'committed', 'other_committed'])
    add_sum(dfv['object_code'].eq('3590') | (dfv['object_code'].str.startswith('35') & ~dfv['object_code'].isin(['3510', '3545', '3590'])), ['fund_balances', 'assigned', 'other_assigned'])
    add_sum(dfv['object_code'].str.startswith('36'), ['fund_balances', 'unassigned'])
    
    # Calculate totals for each fund
    for fund_key in ['general_fund', 'non_major_funds']:
        # Total Assets
        statement['assets']['total_assets'][fund_key] = (
            statement['assets']['cash_and_equivalents'][fund_key] +
            statement['assets']['taxes_receivable'][fund_key] +
            statement['assets']['due_from_other_governments'][fund_key] +
            statement['assets']['due_from_other_funds'][fund_key] +
            statement['assets']['other_receivables'][fund_key] +
            statement['assets']['inventories'][fund_key] +
            statement['assets']['unrealized_expenditures'][fund_key]
        )
        
        # Total Liabilities
        statement['liabilities']['total_liabilities'][fund_key] = (
            statement['liabilities']['current_liabilities']['accounts_payable'][fund_key] +
            statement['liabilities']['current_liabilities']['payroll_deductions'][fund_key] +
            statement['liabilities']['current_liabilities']['accrued_wages'][fund_key] +
            statement['liabilities']['current_liabilities']['due_to_other_funds'][fund_key] +
            statement['liabilities']['current_liabilities']['due_to_other_governments'][fund_key] +
            statement['liabilities']['current_liabilities']['unearned_revenue'][fund_key]
        )
        
        # Total Deferred Inflows
        statement['deferred_inflows']['total_deferred_inflows'][fund_key] = (
            statement['deferred_inflows']['unavailable_revenue_property_taxes'][fund_key]
        )
        
        # Total Fund Balances
        statement['fund_balances']['total_fund_balances'][fund_key] = (
            statement['fund_balances']['nonspendable']['inventories'][fund_key] +
            statement['fund_balances']['nonspendable']['prepaid_items'][fund_key] +
            statement['fund_balances']['restricted']['federal_state_funds'][fund_key] +
            statement['fund_balances']['restricted']['retirement_long_term_debt'][fund_key] +
            statement['fund_balances']['restricted']['other_restrictions'][fund_key] +
            statement['fund_balances']['committed']['construction'][fund_key] +
            statement['fund_balances']['committed']['other_committed'][fund_key] +
            statement['fund_balances']['assigned']['other_assigned'][fund_key] +
            statement['fund_balances']['unassigned'][fund_key]
        )
        
        # Total Liabilities, Deferred Inflows and Fund Balances
        statement['total_liabilities_deferred_fund_balances'][fund_key] = (
            statement['liabilities']['total_liabilities'][fund_key] +
            statement['deferred_inflows']['total_deferred_inflows'][fund_key] +
            statement['fund_balances']['total_fund_balances'][fund_key]
        )
    
    return statement

def generate_governmental_funds_revenues_expenditures(df: pd.DataFrame, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Statement of Revenues, Expenditures, and Changes in Fund Balances - Governmental Funds
    in the exact format provided by the user.
    Structure shows revenues, expenditures, and changes in fund balances by fund type.
    """
    
    # Initialize detailed statement structure matching the provided format
    statement = {
        "title": "STATEMENT OF REVENUES, EXPENDITURES, AND CHANGES IN FUND BALANCES - GOVERNMENTAL FUNDS",
        "funds": {
            "general_fund": "General Fund",
            "non_major_funds": "Non-Major Funds"
        },
        "revenues": {
            "local_intermediate_sources": {"code": "5700", "description": "Local and Intermediate Sources", "general_fund": 0, "non_major_funds": 0},
            "state_program_revenues": {"code": "5800", "description": "State Program Revenues", "general_fund": 0, "non_major_funds": 0},
            "federal_program_revenues": {"code": "5900", "description": "Federal Program Revenues", "general_fund": 0, "non_major_funds": 0},
            "total_revenues": {"code": "5020", "description": "Total Revenues", "general_fund": 0, "non_major_funds": 0}
        },
        "expenditures": {
            "current": {
                "instruction": {"code": "0011", "description": "Instruction", "general_fund": 0, "non_major_funds": 0},
                "instructional_resources": {"code": "0012", "description": "Instructional Resources and Media Services", "general_fund": 0, "non_major_funds": 0},
                "curriculum_staff_dev": {"code": "0013", "description": "Curriculum and Staff Development", "general_fund": 0, "non_major_funds": 0},
                "instructional_leadership": {"code": "0021", "description": "Instructional Leadership", "general_fund": 0, "non_major_funds": 0},
                "school_leadership": {"code": "0023", "description": "School Leadership", "general_fund": 0, "non_major_funds": 0},
                "guidance_counseling": {"code": "0031", "description": "Guidance, Counseling, and Evaluation Services", "general_fund": 0, "non_major_funds": 0},
                "social_work": {"code": "0032", "description": "Social Work Services", "general_fund": 0, "non_major_funds": 0},
                "health_services": {"code": "0033", "description": "Health Services", "general_fund": 0, "non_major_funds": 0},
                "student_transportation": {"code": "0034", "description": "Student Transportation", "general_fund": 0, "non_major_funds": 0},
                "food_service": {"code": "0035", "description": "Food Service", "general_fund": 0, "non_major_funds": 0},
                "cocurricular": {"code": "0036", "description": "Cocurricular/Extracurricular Activities", "general_fund": 0, "non_major_funds": 0},
                "general_admin": {"code": "0041", "description": "General Administration", "general_fund": 0, "non_major_funds": 0},
                "facilities_maintenance": {"code": "0051", "description": "Facilities Maintenance and Operations", "general_fund": 0, "non_major_funds": 0},
                "security_monitoring": {"code": "0052", "description": "Security and Monitoring Services", "general_fund": 0, "non_major_funds": 0},
                "data_processing": {"code": "0053", "description": "Data Processing Services", "general_fund": 0, "non_major_funds": 0},
                "community_services": {"code": "0061", "description": "Community Services", "general_fund": 0, "non_major_funds": 0},
                "principal_long_term_debt": {"code": "0071", "description": "Principal on Long-term Debt", "general_fund": 0, "non_major_funds": 0},
                "interest_long_term_debt": {"code": "0072", "description": "Interest on Long-term Debt", "general_fund": 0, "non_major_funds": 0},
                "bond_issuance_costs": {"code": "0073", "description": "Bond Issuance Costs and Fees", "general_fund": 0, "non_major_funds": 0},
                "capital_outlay": {"code": "0081", "description": "Capital Outlay", "general_fund": 0, "non_major_funds": 0},
                "shared_service_arrangements": {"code": "0093", "description": "Payments to Shared Service Arrangements", "general_fund": 0, "non_major_funds": 0},
                "other_intergovernmental": {"code": "0099", "description": "Other Intergovernmental Charges", "general_fund": 0, "non_major_funds": 0}
            },
            "total_expenditures": {"code": "6030", "description": "Total Expenditures", "general_fund": 0, "non_major_funds": 0}
        },
        "excess_deficiency": {"code": "1100", "description": "Excess (Deficiency) of Revenues Over (Under) Expenditures", "general_fund": 0, "non_major_funds": 0},
        "other_financing": {
            "sale_property": {"code": "7912", "description": "Sale of Real or Personal Property", "general_fund": 0, "non_major_funds": 0},
            "transfers_in": {"code": "7915", "description": "Transfers In", "general_fund": 0, "non_major_funds": 0},
            "premium_bond_remarketing": {"code": "7916", "description": "Premium on Bond Remarketing", "general_fund": 0, "non_major_funds": 0},
            "other_resources": {"code": "7949", "description": "Other Resources", "general_fund": 0, "non_major_funds": 0},
            "transfers_out": {"code": "8911", "description": "Transfers Out", "general_fund": 0, "non_major_funds": 0},
            "total_other_financing": {"code": "7080", "description": "Total Other Financing Sources and (Uses)", "general_fund": 0, "non_major_funds": 0}
        },
        "net_change": {"code": "1200", "description": "Net Change in Fund Balances", "general_fund": 0, "non_major_funds": 0},
        "fund_balances": {
            "beginning": {"code": "0100", "description": "Fund Balances - Beginning", "general_fund": 0, "non_major_funds": 0},
            "ending": {"code": "3000", "description": "Fund Balances - Ending", "general_fund": 0, "non_major_funds": 0}
        }
    }
    
    # Vectorized aggregation
    if df.empty:
        return statement

    dfv = df.copy()
    dfv['account_code'] = dfv['account_code'].astype(str)
    dfv['object_code'] = dfv['account_code'].str.slice(5, 9)
    dfv['function_code'] = dfv['account_code'].str.slice(3, 5)
    dfv['amount'] = pd.to_numeric(dfv.get('current_year_actual', 0), errors='coerce').fillna(0)

    # Build mapping DataFrame
    map_df = pd.DataFrame.from_dict(mapping, orient='index') if mapping else pd.DataFrame()
    if not map_df.empty and 'account_code' not in map_df.columns:
        map_df['account_code'] = map_df.index
    if not map_df.empty:
        dfv = dfv.merge(map_df[['account_code', 'fund_category']], on='account_code', how='left')
    else:
        dfv['fund_category'] = 'general_fund'
    dfv['fund_key'] = dfv['fund_category'].apply(lambda x: 'general_fund' if x == 'general_fund' else 'non_major_funds')

    def add_sum(mask, target_path):
        sums = dfv[mask].groupby('fund_key')['amount'].sum()
        for fk, val in sums.items():
            node = statement
            for key in target_path[:-1]:
                node = node[key]
            node[target_path[-1]][fk] += float(val)

    # Revenues
    add_sum(dfv['object_code'].str.startswith('57'), ['revenues', 'local_intermediate_sources'])
    add_sum(dfv['object_code'].str.startswith('58'), ['revenues', 'state_program_revenues'])
    add_sum(dfv['object_code'].str.startswith('59'), ['revenues', 'federal_program_revenues'])
    # Default revenue bucket for other 5xxx
    add_sum(dfv['object_code'].str.startswith('5') & ~dfv['object_code'].str.match(r'57|58|59'), ['revenues', 'local_intermediate_sources'])

    # Expenditures by function codes
    exp_map = {
        '11': ['expenditures', 'current', 'instruction'],
        '12': ['expenditures', 'current', 'instructional_resources'],
        '13': ['expenditures', 'current', 'curriculum_staff_dev'],
        '21': ['expenditures', 'current', 'instructional_leadership'],
        '23': ['expenditures', 'current', 'school_leadership'],
        '31': ['expenditures', 'current', 'guidance_counseling'],
        '32': ['expenditures', 'current', 'social_work'],
        '33': ['expenditures', 'current', 'health_services'],
        '34': ['expenditures', 'current', 'student_transportation'],
        '35': ['expenditures', 'current', 'food_service'],
        '36': ['expenditures', 'current', 'cocurricular'],
        '41': ['expenditures', 'current', 'general_admin'],
        '51': ['expenditures', 'current', 'facilities_maintenance'],
        '52': ['expenditures', 'current', 'security_monitoring'],
        '53': ['expenditures', 'current', 'data_processing'],
        '61': ['expenditures', 'current', 'community_services'],
        '71': ['expenditures', 'current', 'principal_long_term_debt'],
        '72': ['expenditures', 'current', 'interest_long_term_debt'],
        '73': ['expenditures', 'current', 'bond_issuance_costs'],
        '81': ['expenditures', 'current', 'capital_outlay'],
        '93': ['expenditures', 'current', 'shared_service_arrangements'],
        '99': ['expenditures', 'current', 'other_intergovernmental'],
    }
    for fcode, path in exp_map.items():
        add_sum(dfv['object_code'].str.startswith('6') & dfv['function_code'].eq(fcode), path)
    # Default bucket for unmapped 6xxx
    add_sum(dfv['object_code'].str.startswith('6') & (~dfv['function_code'].isin(list(exp_map.keys()))), ['expenditures', 'current', 'general_admin'])

    # Other financing sources and uses
    add_sum(dfv['object_code'].eq('7912'), ['other_financing', 'sale_property'])
    add_sum(dfv['object_code'].eq('7915'), ['other_financing', 'transfers_in'])
    add_sum(dfv['object_code'].eq('7916'), ['other_financing', 'premium_bond_remarketing'])
    add_sum(dfv['object_code'].eq('7949'), ['other_financing', 'other_resources'])
    add_sum(dfv['object_code'].str.startswith('79') & ~dfv['object_code'].isin(['7912', '7915', '7916', '7949']), ['other_financing', 'other_resources'])
    add_sum(dfv['object_code'].eq('8911') | dfv['object_code'].str.startswith('8'), ['other_financing', 'transfers_out'])
    
    # Calculate totals for each fund
    for fund_key in ['general_fund', 'non_major_funds']:
        # Total Revenues
        statement['revenues']['total_revenues'][fund_key] = (
            statement['revenues']['local_intermediate_sources'][fund_key] +
            statement['revenues']['state_program_revenues'][fund_key] +
            statement['revenues']['federal_program_revenues'][fund_key]
        )
        
        # Total Expenditures
        statement['expenditures']['total_expenditures'][fund_key] = (
            statement['expenditures']['current']['instruction'][fund_key] +
            statement['expenditures']['current']['instructional_resources'][fund_key] +
            statement['expenditures']['current']['curriculum_staff_dev'][fund_key] +
            statement['expenditures']['current']['instructional_leadership'][fund_key] +
            statement['expenditures']['current']['school_leadership'][fund_key] +
            statement['expenditures']['current']['guidance_counseling'][fund_key] +
            statement['expenditures']['current']['social_work'][fund_key] +
            statement['expenditures']['current']['health_services'][fund_key] +
            statement['expenditures']['current']['student_transportation'][fund_key] +
            statement['expenditures']['current']['food_service'][fund_key] +
            statement['expenditures']['current']['cocurricular'][fund_key] +
            statement['expenditures']['current']['general_admin'][fund_key] +
            statement['expenditures']['current']['facilities_maintenance'][fund_key] +
            statement['expenditures']['current']['security_monitoring'][fund_key] +
            statement['expenditures']['current']['data_processing'][fund_key] +
            statement['expenditures']['current']['community_services'][fund_key] +
            statement['expenditures']['current']['principal_long_term_debt'][fund_key] +
            statement['expenditures']['current']['interest_long_term_debt'][fund_key] +
            statement['expenditures']['current']['bond_issuance_costs'][fund_key] +
            statement['expenditures']['current']['capital_outlay'][fund_key] +
            statement['expenditures']['current']['shared_service_arrangements'][fund_key] +
            statement['expenditures']['current']['other_intergovernmental'][fund_key]
        )
        
        # Excess (Deficiency) of Revenues Over (Under) Expenditures
        statement['excess_deficiency'][fund_key] = (
            statement['revenues']['total_revenues'][fund_key] -
            statement['expenditures']['total_expenditures'][fund_key]
        )
        
        # Total Other Financing Sources and (Uses)
        statement['other_financing']['total_other_financing'][fund_key] = (
            statement['other_financing']['sale_property'][fund_key] +
            statement['other_financing']['transfers_in'][fund_key] +
            statement['other_financing']['premium_bond_remarketing'][fund_key] +
            statement['other_financing']['other_resources'][fund_key] +
            statement['other_financing']['transfers_out'][fund_key]
        )
        
        # Net Change in Fund Balances
        statement['net_change'][fund_key] = (
            statement['excess_deficiency'][fund_key] +
            statement['other_financing']['total_other_financing'][fund_key]
        )
        
        # Set beginning fund balances (this would typically come from previous year data)
        # For now, we'll use example values
        statement['fund_balances']['beginning'][fund_key] = 25217718 if fund_key == 'general_fund' else 4550784
        
        # Fund Balances - Ending
        statement['fund_balances']['ending'][fund_key] = (
            statement['fund_balances']['beginning'][fund_key] +
            statement['net_change'][fund_key]
        )
    
    return statement

def get_statement_mapping_info(account_code: str, gasb_category: str, object_code: str, function_code: str) -> dict:
    """Determine which statement and line item an account maps to"""
    
    # Default values
    statement_type = 'Unknown'
    statement_section = 'Unknown'
    statement_line_code = 'XX'
    statement_line_description = 'Unmapped Account'
    
    if gasb_category == 'Unmapped':
        return {
            'statement_type': statement_type,
            'statement_section': statement_section,
            'statement_line_code': statement_line_code,
            'statement_line_description': statement_line_description
        }
    
    # Map to statement types and sections
    if gasb_category in ['current_assets', 'capital_assets', 'deferred_outflows', 'current_liabilities', 'long_term_liabilities', 'deferred_inflows', 'net_investment_capital_assets', 'restricted_net_position', 'unrestricted_net_position']:
        statement_type = 'Net Position'
        
        if gasb_category in ['current_assets', 'capital_assets']:
            statement_section = 'ASSETS'
            if object_code.startswith('11'):
                statement_line_code = '1110'
                statement_line_description = 'Cash and Cash Equivalents'
            elif object_code.startswith('12'):
                if object_code == '1225':
                    statement_line_code = '1225'
                    statement_line_description = 'Property Taxes Receivable (Net)'
                elif object_code == '1240':
                    statement_line_code = '1240'
                    statement_line_description = 'Due from Other Governments'
                elif object_code == '1267':
                    statement_line_code = '1267'
                    statement_line_description = 'Due from Fiduciary'
                else:
                    statement_line_code = '1290'
                    statement_line_description = 'Other Receivables (Net)'
            elif object_code.startswith('13'):
                statement_line_code = '1300'
                statement_line_description = 'Inventories'
            elif object_code.startswith('14'):
                statement_line_code = '1410'
                statement_line_description = 'Unrealized Expenses'
            elif object_code.startswith('15'):
                if object_code == '1510':
                    statement_line_code = '1510'
                    statement_line_description = 'Land'
                elif object_code == '1520':
                    statement_line_code = '1520'
                    statement_line_description = 'Buildings and Improvements, Net'
                elif object_code == '1530':
                    statement_line_code = '1530'
                    statement_line_description = 'Furniture and Equipment, Net'
                elif object_code == '1580':
                    statement_line_code = '1580'
                    statement_line_description = 'Construction in Progress'
                else:
                    statement_line_code = '1520'
                    statement_line_description = 'Buildings and Improvements, Net'
        
        elif gasb_category == 'deferred_outflows':
            statement_section = 'DEFERRED OUTFLOWS OF RESOURCES'
            if object_code == '1701':
                statement_line_code = '1701'
                statement_line_description = 'Deferred Charge for Refunding'
            elif object_code == '1705':
                statement_line_code = '1705'
                statement_line_description = 'Deferred Outflow Related to Pensions'
            elif object_code == '1706':
                statement_line_code = '1706'
                statement_line_description = 'Deferred Outflow Related to OPEB'
            else:
                statement_line_code = '1701'
                statement_line_description = 'Deferred Charge for Refunding'
        
        elif gasb_category in ['current_liabilities', 'long_term_liabilities']:
            statement_section = 'LIABILITIES'
            if object_code.startswith('21'):
                if object_code == '2110':
                    statement_line_code = '2110'
                    statement_line_description = 'Accounts Payable'
                elif object_code == '2140':
                    statement_line_code = '2140'
                    statement_line_description = 'Interest Payable'
                elif object_code == '2165':
                    statement_line_code = '2165'
                    statement_line_description = 'Accrued Liabilities'
                elif object_code == '2180':
                    statement_line_code = '2180'
                    statement_line_description = 'Due to Other Governments'
                elif object_code == '2300':
                    statement_line_code = '2300'
                    statement_line_description = 'Unearned Revenue'
                else:
                    statement_line_code = '2110'
                    statement_line_description = 'Accounts Payable'
            elif object_code.startswith('25'):
                if object_code == '2501':
                    statement_line_code = '2501'
                    statement_line_description = 'Due Within One Year'
                elif object_code == '2502':
                    statement_line_code = '2502'
                    statement_line_description = 'Due in More Than One Year'
                elif object_code == '2540':
                    statement_line_code = '2540'
                    statement_line_description = 'Net Pension Liability'
                elif object_code == '2545':
                    statement_line_code = '2545'
                    statement_line_description = 'Net OPEB Liability'
                else:
                    statement_line_code = '2502'
                    statement_line_description = 'Due in More Than One Year'
        
        elif gasb_category == 'deferred_inflows':
            statement_section = 'DEFERRED INFLOWS OF RESOURCES'
            if object_code == '2605':
                statement_line_code = '2605'
                statement_line_description = 'Deferred Inflow Related to Pensions'
            elif object_code == '2606':
                statement_line_code = '2606'
                statement_line_description = 'Deferred Inflow Related to OPEB'
            else:
                statement_line_code = '2605'
                statement_line_description = 'Deferred Inflow Related to Pensions'
        
        elif gasb_category in ['net_investment_capital_assets', 'restricted_net_position', 'unrestricted_net_position']:
            statement_section = 'NET POSITION'
            if gasb_category == 'net_investment_capital_assets':
                statement_line_code = '3200'
                statement_line_description = 'Net Investment in Capital Assets'
            elif gasb_category == 'restricted_net_position':
                if object_code == '3820':
                    statement_line_code = '3820'
                    statement_line_description = 'State and Federal Programs'
                elif object_code == '3850':
                    statement_line_code = '3850'
                    statement_line_description = 'Debt Service'
                else:
                    statement_line_code = '3820'
                    statement_line_description = 'State and Federal Programs'
            elif gasb_category == 'unrestricted_net_position':
                statement_line_code = '3900'
                statement_line_description = 'Unrestricted'
    
    elif gasb_category in ['program_expenses', 'general_expenses', 'program_revenues', 'general_revenues', 'other_resources', 'other_uses']:
        statement_type = 'Activities'
        
        if gasb_category in ['program_expenses', 'general_expenses']:
            statement_section = 'Governmental Activities'
            # Map function codes to specific programs
            if function_code == '11':
                statement_line_code = '11'
                statement_line_description = 'Instruction'
            elif function_code == '12':
                statement_line_code = '12'
                statement_line_description = 'Instructional Resources and Media Services'
            elif function_code == '13':
                statement_line_code = '13'
                statement_line_description = 'Curriculum and Staff Development'
            elif function_code == '21':
                statement_line_code = '21'
                statement_line_description = 'Instructional Leadership'
            elif function_code == '23':
                statement_line_code = '23'
                statement_line_description = 'School Leadership'
            elif function_code == '31':
                statement_line_code = '31'
                statement_line_description = 'Guidance, Counseling, and Evaluation Services'
            elif function_code == '32':
                statement_line_code = '32'
                statement_line_description = 'Social Work Services'
            elif function_code == '33':
                statement_line_code = '33'
                statement_line_description = 'Health Services'
            elif function_code == '34':
                statement_line_code = '34'
                statement_line_description = 'Student Transportation'
            elif function_code == '35':
                statement_line_code = '35'
                statement_line_description = 'Food Service'
            elif function_code == '36':
                statement_line_code = '36'
                statement_line_description = 'Cocurricular/Extracurricular Activities'
            elif function_code == '41':
                statement_line_code = '41'
                statement_line_description = 'General Administration'
            elif function_code == '51':
                statement_line_code = '51'
                statement_line_description = 'Facilities Maintenance and Operations'
            elif function_code == '52':
                statement_line_code = '52'
                statement_line_description = 'Security and Monitoring Services'
            elif function_code == '53':
                statement_line_code = '53'
                statement_line_description = 'Data Processing Services'
            elif function_code == '61':
                statement_line_code = '61'
                statement_line_description = 'Community Services'
            elif function_code == '72':
                statement_line_code = '72'
                statement_line_description = 'Interest on Long-term Debt'
            elif function_code == '73':
                statement_line_code = '73'
                statement_line_description = 'Bond Issuance Costs and Fees'
            elif function_code == '81':
                statement_line_code = '81'
                statement_line_description = 'Capital Outlay'
            elif function_code == '93':
                statement_line_code = '93'
                statement_line_description = 'Payments Related to Shared Services Arrangements'
            elif function_code == '99':
                statement_line_code = '99'
                statement_line_description = 'Other Intergovernmental Charges'
            else:
                statement_line_code = '41'
                statement_line_description = 'General Administration'
        
        elif gasb_category in ['program_revenues', 'general_revenues']:
            statement_section = 'General Revenues'
            if gasb_category == 'program_revenues':
                statement_line_code = 'PR'
                statement_line_description = 'Program Revenues'
            else:
                statement_line_code = 'MT'
                statement_line_description = 'Property Taxes, Levied for General Purposes'
        
        elif gasb_category == 'other_resources':
            statement_section = 'General Revenues'
            if object_code == '7915':
                statement_line_code = '7915'
                statement_line_description = 'Other Resources'
            elif object_code.startswith('70'):
                statement_line_code = '70'
                statement_line_description = 'Investment Earnings'
            elif object_code.startswith('72'):
                statement_line_code = '72'
                statement_line_description = 'Transfers In'
            elif object_code.startswith('74'):
                statement_line_code = '74'
                statement_line_description = 'Proceeds from Debt'
            else:
                statement_line_code = '79'
                statement_line_description = 'Other Resources'
        
        elif gasb_category == 'other_uses':
            statement_section = 'Governmental Activities'
            if object_code.startswith('80'):
                statement_line_code = '80'
                statement_line_description = 'Interest Expense'
            elif object_code.startswith('82'):
                statement_line_code = '82'
                statement_line_description = 'Transfers Out'
            elif object_code.startswith('84'):
                statement_line_code = '84'
                statement_line_description = 'Principal Payments on Debt'
            else:
                statement_line_code = '89'
                statement_line_description = 'Other Uses'
    
    # For governmental funds statements, determine if it's balance sheet or revenues/expenditures
    elif object_code.startswith('1') or object_code.startswith('2') or object_code.startswith('3'):
        statement_type = 'Balance Sheet'
        if object_code.startswith('1'):
            statement_section = 'ASSETS'
        elif object_code.startswith('2'):
            statement_section = 'LIABILITIES'
        elif object_code.startswith('3'):
            statement_section = 'FUND BALANCES'
    elif object_code.startswith('5') or object_code.startswith('6'):
        statement_type = 'Revenues & Expenditures'
        if object_code.startswith('5'):
            statement_section = 'REVENUES'
        elif object_code.startswith('6'):
            statement_section = 'EXPENDITURES'
    
    return {
        'statement_type': statement_type,
        'statement_section': statement_section,
        'statement_line_code': statement_line_code,
        'statement_line_description': statement_line_description
    }

def get_rollup_information(account_code: str, gasb_category: str, object_code: str) -> dict:
    """Determine if an account is rolled up and provide rollup details"""
    
    rollup_applied = False
    rollup_description = ''
    
    if gasb_category == 'Unmapped':
        return {
            'rollup_applied': rollup_applied,
            'rollup_description': rollup_description
        }
    
    # Check for rollup scenarios
    if object_code.startswith('11'):  # Cash and equivalents
        rollup_applied = True
        rollup_description = 'Rolled up into Cash and Cash Equivalents'
    elif object_code.startswith('12') and object_code not in ['1225', '1240', '1267']:  # Other receivables
        rollup_applied = True
        rollup_description = 'Rolled up into Other Receivables (Net)'
    elif object_code.startswith('15') and object_code not in ['1510', '1520', '1530', '1580']:  # Other capital assets
        rollup_applied = True
        rollup_description = 'Rolled up into Buildings and Improvements, Net'
    elif object_code.startswith('21') and object_code not in ['2110', '2140', '2165', '2180', '2300']:  # Other current liabilities
        rollup_applied = True
        rollup_description = 'Rolled up into Accounts Payable'
    elif object_code.startswith('25') and object_code not in ['2501', '2502', '2540', '2545']:  # Other long-term liabilities
        rollup_applied = True
        rollup_description = 'Rolled up into Due in More Than One Year'
    elif object_code.startswith('38') and object_code not in ['3820', '3850']:  # Other restricted net position
        rollup_applied = True
        rollup_description = 'Rolled up into State and Federal Programs'
    
    return {
        'rollup_applied': rollup_applied,
        'rollup_description': rollup_description
    }

@app.get("/api/export/excel")
async def export_excel(
    current_user: dict = Depends(get_current_user)
):
    """Export statements to Excel with proper formatting"""
    user_id = current_user["id"]
    
    # Get statements from database
    statements_data = get_financial_statements(user_id, "combined")
    if not statements_data:
        raise HTTPException(status_code=400, detail="No statements generated. Please generate statements first.")
    
    statements = statements_data['statements_json']
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Export each statement to a separate worksheet
        export_net_position_statement(writer, statements.get('government_wide_net_position', {}))
        export_activities_statement(writer, statements.get('government_wide_activities', {}))
        export_balance_sheet_statement(writer, statements.get('governmental_funds_balance', {}))
        export_revenues_expenditures_statement(writer, statements.get('governmental_funds_revenues_expenditures', {}))
    
    output.seek(0)
    
    # Return the Excel file as bytes
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=financial_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        }
    )

def export_net_position_statement(writer, data):
    """Export Statement of Net Position to Excel"""
    if not data or not data.get('title'):
        return
    
    sheet_name = "Net Position"
    rows = []
    
    # Add title
    rows.append([data['title']])
    rows.append([])  # Empty row
    
    # Add headers
    rows.append(['Data Control Codes', 'Description', 'Governmental Activities'])
    rows.append([])  # Empty row
    
    # Helper function to add line items
    def add_line_item(item, indent=False):
        if isinstance(item, dict) and 'code' in item and 'description' in item:
            prefix = '    ' if indent else ''
            rows.append([f"{prefix}{item['code']}", item['description'], item.get('amount', 0)])
    
    # Helper function to add section
    def add_section(title, items):
        rows.append([f"{title}:", "", ""])
        for key, value in items.items():
            if key in ['total_assets', 'total_deferred_outflows', 'total_liabilities', 'total_deferred_inflows', 'total_net_position']:
                add_line_item(value)
            elif isinstance(value, dict) and 'code' in value and 'description' in value:
                add_line_item(value)
            elif isinstance(value, dict) and key == 'capital_assets':
                rows.append(['    Capital Assets:', '', ''])
                for sub_key, sub_value in value.items():
                    add_line_item(sub_value, True)
            elif isinstance(value, dict) and key == 'noncurrent_liabilities':
                rows.append(['    Noncurrent Liabilities:', '', ''])
                for sub_key, sub_value in value.items():
                    add_line_item(sub_value, True)
            elif isinstance(value, dict) and key == 'restricted':
                rows.append(['    Restricted For:', '', ''])
                for sub_key, sub_value in value.items():
                    add_line_item(sub_value, True)
        rows.append([])  # Empty row after section
    
    # Add sections
    add_section('ASSETS', data.get('assets', {}))
    add_section('DEFERRED OUTFLOWS OF RESOURCES', data.get('deferred_outflows', {}))
    add_section('LIABILITIES', data.get('liabilities', {}))
    add_section('DEFERRED INFLOWS OF RESOURCES', data.get('deferred_inflows', {}))
    add_section('NET POSITION', data.get('net_position', {}))
    
    # Add balance validation if available
    if data.get('balance_validation'):
        rows.append(['Balance Validation:', '', ''])
        rows.append(['Left Side (Assets + Deferred Outflows):', '', data['balance_validation'].get('left_side', 0)])
        rows.append(['Right Side (Liabilities + Deferred Inflows + Net Position):', '', data['balance_validation'].get('right_side', 0)])
        balanced = data['balance_validation'].get('balanced', False)
        rows.append(['Balanced:', '', 'YES' if balanced else 'NO'])
    
    # Create DataFrame and write to Excel
    df = pd.DataFrame(rows, columns=['Data Control Codes', 'Description', 'Governmental Activities'])
    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    
    # Format the worksheet
    worksheet = writer.sheets[sheet_name]
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.row == 1:  # Title row
                cell.font = cell.font.copy(bold=True, size=14)
            elif cell.row <= 3:  # Header rows
                cell.font = cell.font.copy(bold=True)
            elif cell.value and isinstance(cell.value, str) and cell.value.endswith(':'):  # Section headers
                cell.font = cell.font.copy(bold=True)
            elif cell.column == 3 and isinstance(cell.value, (int, float)):  # Amount column
                cell.number_format = '$#,##0'
    
    # Adjust column widths
    worksheet.column_dimensions['A'].width = 20
    worksheet.column_dimensions['B'].width = 50
    worksheet.column_dimensions['C'].width = 20

def export_activities_statement(writer, data):
    """Export Statement of Activities to Excel"""
    if not data or not data.get('title'):
        return
    
    sheet_name = "Activities"
    rows = []
    
    # Add title
    rows.append([data['title']])
    rows.append([])  # Empty row
    
    # Add governmental activities section
    rows.append(['Governmental Activities (Program Expenses and Revenues)', ''])
    rows.append([])  # Empty row
    
    # Add headers for governmental activities
    rows.append(['Data Control Codes', 'Functions/Programs', 'Expenses', 'Charges for Services', 'Operating Grants', 'Net (Expense) Revenue'])
    rows.append([])  # Empty row
    
    # Add governmental activities
    for key, program in data.get('governmental_activities', {}).items():
        if key not in ['total_governmental', 'total_primary']:
            rows.append([
                program.get('code', ''),
                program.get('description', ''),
                program.get('expenses', 0),
                program.get('charges_for_services', 0),
                program.get('operating_grants', 0),
                program.get('net_expense_revenue', 0)
            ])
        elif key in ['total_governmental', 'total_primary']:
            rows.append([
                program.get('code', ''),
                program.get('description', ''),
                program.get('expenses', 0),
                program.get('charges_for_services', 0),
                program.get('operating_grants', 0),
                program.get('net_expense_revenue', 0)
            ])
    
    rows.append([])  # Empty row
    
    # Add general revenues section
    rows.append(['General Revenues:', ''])
    rows.append([])  # Empty row
    rows.append(['Data Control Codes', 'Description', 'Amount'])
    rows.append([])  # Empty row
    
    for key, revenue in data.get('general_revenues', {}).items():
        rows.append([
            revenue.get('code', ''),
            revenue.get('description', ''),
            revenue.get('amount', 0)
        ])
    
    rows.append([])  # Empty row
    
    # Add net position section
    rows.append(['Net Position:', ''])
    rows.append([])  # Empty row
    rows.append(['Data Control Codes', 'Description', 'Amount'])
    rows.append([])  # Empty row
    
    for key, item in data.get('net_position', {}).items():
        rows.append([
            item.get('code', ''),
            item.get('description', ''),
            item.get('amount', 0)
        ])
    
    # Create DataFrame and write to Excel
    df = pd.DataFrame(rows, columns=['Code', 'Description', 'Amount1', 'Amount2', 'Amount3', 'Amount4'])
    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    
    # Format the worksheet
    worksheet = writer.sheets[sheet_name]
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.row == 1:  # Title row
                cell.font = cell.font.copy(bold=True, size=14)
            elif cell.row <= 3:  # Header rows
                cell.font = cell.font.copy(bold=True)
            elif cell.value and isinstance(cell.value, str) and cell.value.endswith(':'):  # Section headers
                cell.font = cell.font.copy(bold=True)
            elif cell.column >= 3 and isinstance(cell.value, (int, float)):  # Amount columns
                cell.number_format = '$#,##0'
    
    # Adjust column widths
    worksheet.column_dimensions['A'].width = 15
    worksheet.column_dimensions['B'].width = 50
    for col in ['C', 'D', 'E', 'F']:
        worksheet.column_dimensions[col].width = 18

def export_balance_sheet_statement(writer, data):
    """Export Balance Sheet - Governmental Funds to Excel"""
    if not data or not data.get('title'):
        return
    
    sheet_name = "Balance Sheet"
    rows = []
    
    # Add title
    rows.append([data['title']])
    rows.append([])  # Empty row
    
    # Add headers
    rows.append(['Data Control Codes', 'Description', data.get('funds', {}).get('general_fund', 'General Fund'), data.get('funds', {}).get('non_major_funds', 'Non-Major Funds')])
    rows.append([])  # Empty row
    
    # Helper function to add section
    def add_section(title, items):
        rows.append([f"{title}:", '', '', ''])
        for key, value in items.items():
            if key in ['total_assets', 'total_liabilities', 'total_deferred_inflows', 'total_fund_balances', 'total_liabilities_deferred_fund_balances']:
                rows.append([
                    value.get('code', ''),
                    value.get('description', ''),
                    value.get('general_fund', 0),
                    value.get('non_major_funds', 0)
                ])
            elif isinstance(value, dict) and 'code' in value and 'description' in value:
                rows.append([
                    value.get('code', ''),
                    value.get('description', ''),
                    value.get('general_fund', 0),
                    value.get('non_major_funds', 0)
                ])
            elif isinstance(value, dict) and key == 'current_liabilities':
                rows.append(['    Current Liabilities:', '', '', ''])
                for sub_key, sub_value in value.items():
                    rows.append([
                        sub_value.get('code', ''),
                        sub_value.get('description', ''),
                        sub_value.get('general_fund', 0),
                        sub_value.get('non_major_funds', 0)
                    ])
            elif isinstance(value, dict) and key in ['nonspendable', 'restricted', 'committed', 'assigned']:
                rows.append([f"    {key.title()} Fund Balances:", '', '', ''])
                for sub_key, sub_value in value.items():
                    rows.append([
                        sub_value.get('code', ''),
                        sub_value.get('description', ''),
                        sub_value.get('general_fund', 0),
                        sub_value.get('non_major_funds', 0)
                    ])
        rows.append([])  # Empty row after section
    
    # Add sections
    add_section('ASSETS', data.get('assets', {}))
    add_section('LIABILITIES', data.get('liabilities', {}))
    add_section('DEFERRED INFLOWS OF RESOURCES', data.get('deferred_inflows', {}))
    add_section('FUND BALANCES', data.get('fund_balances', {}))
    
    # Add total liabilities, deferred inflows and fund balances
    if data.get('total_liabilities_deferred_fund_balances'):
        total = data['total_liabilities_deferred_fund_balances']
        rows.append([
            total.get('code', ''),
            total.get('description', ''),
            total.get('general_fund', 0),
            total.get('non_major_funds', 0)
        ])
    
    # Create DataFrame and write to Excel
    df = pd.DataFrame(rows, columns=['Code', 'Description', 'General Fund', 'Non-Major Funds'])
    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    
    # Format the worksheet
    worksheet = writer.sheets[sheet_name]
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.row == 1:  # Title row
                cell.font = cell.font.copy(bold=True, size=14)
            elif cell.row <= 3:  # Header rows
                cell.font = cell.font.copy(bold=True)
            elif cell.value and isinstance(cell.value, str) and cell.value.endswith(':'):  # Section headers
                cell.font = cell.font.copy(bold=True)
            elif cell.column >= 3 and isinstance(cell.value, (int, float)):  # Amount columns
                cell.number_format = '$#,##0'
    
    # Adjust column widths
    worksheet.column_dimensions['A'].width = 15
    worksheet.column_dimensions['B'].width = 50
    worksheet.column_dimensions['C'].width = 18
    worksheet.column_dimensions['D'].width = 18

def export_revenues_expenditures_statement(writer, data):
    """Export Statement of Revenues, Expenditures, and Changes in Fund Balances to Excel"""
    if not data or not data.get('title'):
        return
    
    sheet_name = "Revenues & Expenditures"
    rows = []
    
    # Add title
    rows.append([data['title']])
    rows.append([])  # Empty row
    
    # Add headers
    rows.append(['Data Control Codes', 'Description', data.get('funds', {}).get('general_fund', 'General Fund'), data.get('funds', {}).get('non_major_funds', 'Non-Major Funds')])
    rows.append([])  # Empty row
    
    # Helper function to add section
    def add_section(title, items):
        rows.append([f"{title}:", '', '', ''])
        for key, value in items.items():
            if key in ['total_revenues', 'total_expenditures', 'total_other_financing']:
                rows.append([
                    value.get('code', ''),
                    value.get('description', ''),
                    value.get('general_fund', 0),
                    value.get('non_major_funds', 0)
                ])
            elif isinstance(value, dict) and 'code' in value and 'description' in value:
                rows.append([
                    value.get('code', ''),
                    value.get('description', ''),
                    value.get('general_fund', 0),
                    value.get('non_major_funds', 0)
                ])
            elif isinstance(value, dict) and key == 'current':
                rows.append(['    Current:', '', '', ''])
                for sub_key, sub_value in value.items():
                    rows.append([
                        sub_value.get('code', ''),
                        sub_value.get('description', ''),
                        sub_value.get('general_fund', 0),
                        sub_value.get('non_major_funds', 0)
                    ])
        rows.append([])  # Empty row after section
    
    # Add sections
    add_section('REVENUES', data.get('revenues', {}))
    add_section('EXPENDITURES', data.get('expenditures', {}))
    
    # Add excess (deficiency)
    if data.get('excess_deficiency'):
        excess = data['excess_deficiency']
        rows.append([
            excess.get('code', ''),
            excess.get('description', ''),
            excess.get('general_fund', 0),
            excess.get('non_major_funds', 0)
        ])
    
    # Add other financing
    add_section('Other Financing Sources and (Uses)', data.get('other_financing', {}))
    
    # Add net change
    if data.get('net_change'):
        net_change = data['net_change']
        rows.append([
            net_change.get('code', ''),
            net_change.get('description', ''),
            net_change.get('general_fund', 0),
            net_change.get('non_major_funds', 0)
        ])
    
    # Add fund balances
    if data.get('fund_balances'):
        fund_balances = data['fund_balances']
        if fund_balances.get('beginning'):
            beginning = fund_balances['beginning']
            rows.append([
                beginning.get('code', ''),
                beginning.get('description', ''),
                beginning.get('general_fund', 0),
                beginning.get('non_major_funds', 0)
            ])
        if fund_balances.get('ending'):
            ending = fund_balances['ending']
            rows.append([
                ending.get('code', ''),
                ending.get('description', ''),
                ending.get('general_fund', 0),
                ending.get('non_major_funds', 0)
            ])
    
    # Create DataFrame and write to Excel
    df = pd.DataFrame(rows, columns=['Code', 'Description', 'General Fund', 'Non-Major Funds'])
    df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
    
    # Format the worksheet
    worksheet = writer.sheets[sheet_name]
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.row == 1:  # Title row
                cell.font = cell.font.copy(bold=True, size=14)
            elif cell.row <= 3:  # Header rows
                cell.font = cell.font.copy(bold=True)
            elif cell.value and isinstance(cell.value, str) and cell.value.endswith(':'):  # Section headers
                cell.font = cell.font.copy(bold=True)
            elif cell.column >= 3 and isinstance(cell.value, (int, float)):  # Amount columns
                cell.number_format = '$#,##0'
    
    # Adjust column widths
    worksheet.column_dimensions['A'].width = 15
    worksheet.column_dimensions['B'].width = 50
    worksheet.column_dimensions['C'].width = 18
    worksheet.column_dimensions['D'].width = 18

@app.get("/api/audit-trail")
async def get_audit_trail(
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive audit trail data with detailed mappings"""
    user_id = current_user["id"]
    
    # Get trial balance data from database
    data = get_trial_balance_data(user_id)
    if not data:
        raise HTTPException(status_code=400, detail="No data uploaded. Please upload a file first.")
    
    # Get account mappings from database
    mappings_result = get_account_mappings(user_id, page=1, page_size=10000)  # Get all mappings
    mappings = mappings_result['mappings']
    
    if not mappings:
        raise HTTPException(status_code=400, detail="No account mappings found. Please create mappings first.")
    
    # Generate comprehensive audit trail data (vectorized components)
    df = pd.read_json(data['data_json'])

    # Ensure required numeric columns exist
    for col in ['current_year_actual', 'budget', 'prior_year_actual']:
        if col not in df.columns:
            df[col] = 0

    # Vectorized account code parsing
    account_series = df['account_code'].astype(str).str.pad(width=19, side='right', fillchar='0')
    df_parsed = df.copy()
    df_parsed['fund_code'] = account_series.str.slice(0, 3)
    df_parsed['function_code'] = account_series.str.slice(3, 5)
    df_parsed['object_code'] = account_series.str.slice(5, 9)
    df_parsed['sub_object_code'] = account_series.str.slice(9, 13)
    df_parsed['location_code'] = account_series.str.slice(13, 19)

    # Merge mappings as DataFrame
    if mappings:
        mappings_df = pd.DataFrame.from_dict(mappings, orient='index')
        if 'account_code' not in mappings_df.columns:
            mappings_df['account_code'] = mappings_df.index
        # Keep only expected columns
        expected_cols = ['account_code', 'description', 'tea_category', 'gasb_category', 'fund_category', 'statement_line', 'notes', 'mapping_method', 'mapping_confidence', 'processing_notes']
        for c in expected_cols:
            if c not in mappings_df.columns:
                mappings_df[c] = ''
        df_parsed = df_parsed.merge(mappings_df[expected_cols], on='account_code', how='left')
    else:
        # No mappings: fill defaults
        for c in ['description', 'tea_category', 'gasb_category', 'fund_category', 'statement_line', 'notes']:
            df_parsed[c] = ''

    # Flags and defaults
    df_parsed['unmapped_accounts'] = df_parsed['tea_category'].isna() | (df_parsed['tea_category'] == '')
    df_parsed['tea_category'] = df_parsed['tea_category'].fillna('Unmapped')
    df_parsed['gasb_category'] = df_parsed['gasb_category'].fillna('Unmapped')
    df_parsed['fund_category'] = df_parsed['fund_category'].fillna('Unmapped')
    df_parsed['mapping_method'] = df_parsed.get('mapping_method', pd.Series(index=df_parsed.index)).fillna(
        df_parsed['unmapped_accounts'].map({True: 'unmapped', False: 'auto_mapped'})
    )
    df_parsed['mapping_confidence'] = df_parsed.get('mapping_confidence', pd.Series(index=df_parsed.index)).fillna(
        df_parsed['unmapped_accounts'].map({True: 'none', False: 'medium'})
    )
    df_parsed['processing_notes'] = df_parsed.get('processing_notes', pd.Series(index=df_parsed.index)).fillna(
        df_parsed['unmapped_accounts'].map({True: 'Account not mapped', False: ''})
    )

    # Statement mapping via row-wise apply (kept for correctness)
    def _stmt_map(row):
        info = get_statement_mapping_info(row['account_code'], row['gasb_category'], row['object_code'], row['function_code'])
        return pd.Series([
            info['statement_type'],
            info['statement_section'],
            info['statement_line_code'],
            info['statement_line_description'],
        ], index=['statement_type', 'statement_section', 'statement_line_code', 'statement_line_description'])

    stmt_info = df_parsed.apply(_stmt_map, axis=1)
    df_parsed = pd.concat([df_parsed, stmt_info], axis=1)

    # Rollup info via row-wise apply (logic depends on object_code patterns)
    def _rollup(row):
        info = get_rollup_information(row['account_code'], row['gasb_category'], row['object_code'])
        return pd.Series([info['rollup_applied'], info['rollup_description']], index=['rollup_applied', 'rollup_description'])

    roll_info = df_parsed.apply(_rollup, axis=1)
    df_parsed = pd.concat([df_parsed, roll_info], axis=1)

    # Build audit data records directly from DataFrame
    df_out = df_parsed[[
        'account_code', 'current_year_actual', 'budget', 'prior_year_actual',
        'fund_code', 'function_code', 'object_code', 'sub_object_code', 'location_code', 'unmapped_accounts',
        'tea_category', 'gasb_category', 'fund_category',
        'statement_type', 'statement_section', 'statement_line_code', 'statement_line_description',
        'mapping_method', 'mapping_confidence', 'processing_notes', 'rollup_applied', 'rollup_description',
    ]].copy()

    # Add metadata
    df_out['file_upload_date'] = data.get('created_at', '')
    df_out['processing_timestamp'] = datetime.now().isoformat()
    df_out['user_id'] = user_id
    df_out['version'] = '1.0'

    audit_data = df_out.to_dict(orient='records')
    
    # Save audit trail to database
    save_audit_trail(user_id, audit_data, len(audit_data))

    mapped_records = int((~df_out['unmapped_accounts']).sum())
    unmapped_records = int(df_out['unmapped_accounts'].sum())
    
    return JSONResponse({
        "success": True,
        "audit_data": audit_data,
        "total_records": len(audit_data),
        "mapped_records": mapped_records,
        "unmapped_records": unmapped_records,
        "file_info": {
            'filename': data['filename'],
            'encoding': data['encoding'],
            'delimiter': data['delimiter'],
            'rows': data['rows'],
            'columns': data['columns']
        }
    })

@app.get("/api/export/audit-trail")
async def export_audit_trail(
    current_user: dict = Depends(get_current_user)
):
    """Export comprehensive audit trail to CSV"""
    user_id = current_user["id"]
    
    # Get trial balance data from database
    data = get_trial_balance_data(user_id)
    if not data:
        raise HTTPException(status_code=400, detail="No data uploaded. Please upload a file first.")
    
    # Get account mappings from database
    mappings_result = get_account_mappings(user_id, page=1, page_size=10000)  # Get all mappings
    mappings = mappings_result['mappings']
    
    if not mappings:
        raise HTTPException(status_code=400, detail="No account mappings found. Please create mappings first.")
    
    # Generate comprehensive audit trail data (same logic as get_audit_trail)
    df = pd.read_json(data['data_json'])
    audit_data = []
    
    # Process all accounts in trial balance (both mapped and unmapped)
    for _, row in df.iterrows():
        account_code = str(row['account_code'])
        
        # Get all original trial balance columns
        current_year_actual = row.get('current_year_actual', 0)
        budget = row.get('budget', 0)
        prior_year_actual = row.get('prior_year_actual', 0)
        
        # Parse account code components
        fund_code = account_code[0:3] if len(account_code) >= 3 else '000'
        function_code = account_code[3:5] if len(account_code) >= 5 else '00'
        object_code = account_code[5:9] if len(account_code) >= 9 else '0000'
        sub_object_code = account_code[9:13] if len(account_code) >= 13 else '0000'
        location_code = account_code[13:19] if len(account_code) >= 19 else '000000'
        
        # Check if account is mapped
        is_mapped = account_code in mappings
        unmapped_accounts = not is_mapped
        
        if is_mapped:
            mapping = mappings[account_code]
            tea_category = mapping.get('tea_category', 'Unmapped')
            gasb_category = mapping.get('gasb_category', 'Unmapped')
            fund_category = mapping.get('fund_category', 'Unmapped')
            mapping_method = mapping.get('mapping_method', 'auto_mapped')
            mapping_confidence = mapping.get('mapping_confidence', 'medium')
            processing_notes = mapping.get('processing_notes', '')
        else:
            tea_category = 'Unmapped'
            gasb_category = 'Unmapped'
            fund_category = 'Unmapped'
            mapping_method = 'unmapped'
            mapping_confidence = 'none'
            processing_notes = 'Account not mapped'
        
        # Determine statement mapping
        statement_info = get_statement_mapping_info(account_code, gasb_category, object_code, function_code)
        
        # Determine rollup information
        rollup_info = get_rollup_information(account_code, gasb_category, object_code)
        
        audit_data.append({
            # Original Trial Balance Data
            'account_code': account_code,
            'current_year_actual': current_year_actual,
            'budget': budget,
            'prior_year_actual': prior_year_actual,
            
            # Account Code Breakdown
            'fund_code': fund_code,
            'function_code': function_code,
            'object_code': object_code,
            'sub_object_code': sub_object_code,
            'location_code': location_code,
            'unmapped_accounts': unmapped_accounts,
            
            # Mapping Categories
            'tea_category': tea_category,
            'gasb_category': gasb_category,
            'fund_category': fund_category,
            
            # Statement Mapping
            'statement_type': statement_info['statement_type'],
            'statement_section': statement_info['statement_section'],
            'statement_line_code': statement_info['statement_line_code'],
            'statement_line_description': statement_info['statement_line_description'],
            
            # Processing Information
            'mapping_method': mapping_method,
            'mapping_confidence': mapping_confidence,
            'processing_notes': processing_notes,
            'rollup_applied': rollup_info['rollup_applied'],
            'rollup_description': rollup_info['rollup_description'],
            
            # Metadata
            'file_upload_date': data.get('created_at', ''),
            'processing_timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'version': '1.0'
        })
    
    # Save audit trail to database
    save_audit_trail(user_id, audit_data, len(audit_data))
    
    # Create DataFrame with all columns
    audit_df = pd.DataFrame(audit_data)
    
    # Create CSV with all columns
    output = io.StringIO()
    audit_df.to_csv(output, index=False)
    output.seek(0)
    
    # Return the CSV file as bytes
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

# Add simple authentication routes
app.include_router(auth_router, prefix="/auth", tags=["auth"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# uvicorn main:app --reload --host 0.0.0.0 --port 8000