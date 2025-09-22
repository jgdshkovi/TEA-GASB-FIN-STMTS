"""
Simple authentication endpoints to replace FastAPI Users
"""

import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
import sqlite3
import uuid

# JWT Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

# Database setup
DATABASE_URL = "tea_financial.db"

# Pydantic models
class UserCreate(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization: Optional[str] = None

class UserRead(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False

class UserLogin(BaseModel):
    username: str  # This will be the email
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Database functions
def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            organization TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_verified BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create trial_balance_data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trial_balance_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            encoding TEXT,
            delimiter TEXT,
            rows INTEGER,
            columns INTEGER,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create account_mappings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS account_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            account_code TEXT NOT NULL,
            description TEXT,
            tea_category TEXT,
            gasb_category TEXT,
            fund_category TEXT,
            statement_line TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, account_code)
        )
    ''')
    
    # Create financial_statements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            statement_type TEXT NOT NULL,
            statement_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            audit_data TEXT NOT NULL,
            total_records INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Database functions for mappings and data
def save_trial_balance_data(user_id: str, filename: str, encoding: str, delimiter: str, rows: int, columns: int, data_json: str):
    """Save trial balance data to database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Delete existing data for this user
    cursor.execute("DELETE FROM trial_balance_data WHERE user_id = ?", (user_id,))
    
    # Insert new data
    cursor.execute('''
        INSERT INTO trial_balance_data (user_id, filename, encoding, delimiter, rows, columns, data_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, filename, encoding, delimiter, rows, columns, data_json))
    
    conn.commit()
    conn.close()

def get_trial_balance_data(user_id: str):
    """Get trial balance data from database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT filename, encoding, delimiter, rows, columns, data_json, created_at
        FROM trial_balance_data 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'filename': result[0],
            'encoding': result[1],
            'delimiter': result[2],
            'rows': result[3],
            'columns': result[4],
            'data_json': result[5],
            'created_at': result[6]
        }
    return None

def save_account_mappings(user_id: str, mappings: dict):
    """Save account mappings to database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # If empty mappings dict, delete all mappings for this user
    if not mappings:
        cursor.execute("DELETE FROM account_mappings WHERE user_id = ?", (user_id,))
    else:
        for account_code, mapping_data in mappings.items():
            if mapping_data is None:
                # Delete mapping
                cursor.execute("DELETE FROM account_mappings WHERE user_id = ? AND account_code = ?", (user_id, account_code))
            else:
                # Insert or update mapping
                cursor.execute('''
                    INSERT OR REPLACE INTO account_mappings 
                    (user_id, account_code, description, tea_category, gasb_category, fund_category, statement_line, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    user_id, 
                    account_code,
                    mapping_data.get('description', ''),
                    mapping_data.get('tea_category', ''),
                    mapping_data.get('gasb_category', ''),
                    mapping_data.get('fund_category', ''),
                    mapping_data.get('statement_line', 'XX'),
                    mapping_data.get('notes', '')
                ))
    
    conn.commit()
    conn.close()

def get_account_mappings(user_id: str, page: int = 1, page_size: int = 100, search: str = None):
    """Get account mappings from database with pagination"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Build search condition
    search_condition = ""
    search_params = [user_id]
    
    if search:
        search_lower = search.lower()
        # GASB category display names mapping
        gasb_display_names = {
            'current_assets': 'current assets',
            'capital_assets': 'capital assets', 
            'deferred_outflows': 'deferred outflows of resources',
            'current_liabilities': 'current liabilities',
            'long_term_liabilities': 'long-term liabilities',
            'deferred_inflows': 'deferred inflows of resources',
            'net_investment_capital_assets': 'net investment in capital assets',
            'restricted_net_position': 'restricted net position',
            'unrestricted_net_position': 'unrestricted net position',
            'program_revenues': 'program revenues',
            'general_revenues': 'general revenues',
            'program_expenses': 'program expenses',
            'general_expenses': 'general expenses'
        }
        
        search_condition = '''
            AND (
                LOWER(account_code) LIKE ? OR
                LOWER(description) LIKE ? OR
                LOWER(tea_category) LIKE ? OR
                LOWER(gasb_category) LIKE ? OR
                LOWER(fund_category) LIKE ?
            )
        '''
        search_params.extend([f'%{search_lower}%'] * 5)
    
    # Get total count
    count_query = f"SELECT COUNT(*) FROM account_mappings WHERE user_id = ? {search_condition}"
    cursor.execute(count_query, search_params)
    total_items = cursor.fetchone()[0]
    
    # Calculate pagination
    total_pages = (total_items + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get paginated results
    query = f'''
        SELECT account_code, description, tea_category, gasb_category, fund_category, statement_line, notes
        FROM account_mappings 
        WHERE user_id = ? {search_condition}
        ORDER BY account_code
        LIMIT ? OFFSET ?
    '''
    cursor.execute(query, search_params + [page_size, offset])
    
    results = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary format
    mappings = {}
    for row in results:
        mappings[row[0]] = {
            'account_code': row[0],
            'description': row[1] or '',
            'tea_category': row[2] or '',
            'gasb_category': row[3] or '',
            'fund_category': row[4] or '',
            'statement_line': row[5] or 'XX',
            'notes': row[6] or ''
        }
    
    return {
        'mappings': mappings,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_items': total_items,
            'total_pages': total_pages
        }
    }

def get_user_by_email(email: str):
    """Get user by email"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "email": user[1],
            "hashed_password": user[2],
            "first_name": user[3],
            "last_name": user[4],
            "organization": user[5],
            "is_active": bool(user[6]),
            "is_verified": bool(user[7]),
            "created_at": user[8]
        }
    return None

def create_user(email: str, password: str, first_name: str = None, last_name: str = None, organization: str = None):
    """Create a new user"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    user_id = str(uuid.uuid4())
    hashed_password = pwd_context.hash(password)
    
    try:
        cursor.execute('''
            INSERT INTO users (id, email, hashed_password, first_name, last_name, organization)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, hashed_password, first_name, last_name, organization))
        
        conn.commit()
        conn.close()
        
        return {
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "organization": organization,
            "is_active": True,
            "is_verified": False
        }
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="User with this email already exists")

def verify_password(plain_password: str, hashed_password: str):
    """Verify a password"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_email(user_id)
    if user is None:
        raise credentials_exception
    
    return user

# Router
router = APIRouter()

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """Register a new user"""
    # Validate password strength
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Create user
    user = create_user(
        email=user_data.email,
        password=user_data.password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        organization=user_data.organization
    )
    
    return UserRead(**user)

@router.post("/login", response_model=Token)
async def login(username: str = Form(...), password: str = Form(...)):
    """Login user"""
    user = get_user_by_email(username)
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

def save_financial_statements(user_id: str, statement_type: str, statement_data: dict):
    """Save financial statements to database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO financial_statements 
        (user_id, statement_type, statement_data, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, statement_type, json.dumps(statement_data)))
    
    conn.commit()
    conn.close()

def get_financial_statements(user_id: str, statement_type: str):
    """Get financial statements from database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT statement_data, created_at
        FROM financial_statements 
        WHERE user_id = ? AND statement_type = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (user_id, statement_type))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'statements_json': json.loads(result[0]),
            'created_at': result[1]
        }
    return None

def save_audit_trail(user_id: str, audit_data: list, total_records: int):
    """Save audit trail data to database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO audit_trails 
        (user_id, audit_data, total_records, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, json.dumps(audit_data), total_records))
    
    conn.commit()
    conn.close()

def get_audit_trail(user_id: str):
    """Get audit trail data from database"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT audit_data, total_records, created_at
        FROM audit_trails 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'audit_data': json.loads(result[0]),
            'total_records': result[1],
            'created_at': result[2]
        }
    return None

def clear_audit_trail(user_id: str):
    """Clear audit trail data for a user"""
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM audit_trails WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Get current user"""
    return UserRead(**current_user)

# Initialize database
init_db()
