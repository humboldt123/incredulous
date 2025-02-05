from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess
import tempfile
import os
import pandas as pd
from openai import OpenAI
import json
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path
import time
import io
from io import StringIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=open('secret').read().strip())

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_statement_format(sample_text: str) -> Dict[str, Any]:
    """Use OpenAI to detect date format and statement structure with improved error handling"""
    prompt = """
    Analyze this bank statement and return a JSON object with format details.
    Only analyze the visible transaction entries.
    
    Return a JSON object with these exact keys:
    {
        "date_format": "string, e.g. DD MMM YY",
        "amount_format": "string, e.g. 1234.56",
        "column_order": ["date", "description", "debit", "credit", "balance"],
        "credit_marker": "string, e.g. separate_column",
        "debit_marker": "string, e.g. separate_column",
        "null_marker": "string, e.g. empty string"
    }
    
    If you can't determine any field, use these defaults:
    - date_format: "DD MMM YY" 
    - amount_format: "1234.56"
    - column_order: ["date", "description", "debit", "credit", "balance"]
    - credit_marker: "separate_column"
    - debit_marker: "separate_column"
    - null_marker: ""
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a bank statement format analyzer. Return only valid JSON format analysis."
                },
                {
                    "role": "user", 
                    "content": f"{prompt}\n\nStatement text:\n{sample_text[:2000]}"
                }
            ],
            response_format={ "type": "json_object" },
            temperature=0
        )
        
        # Parse response with fallback to defaults
        try:
            format_info = json.loads(response.choices[0].message.content.strip())
            
            # Validate required keys
            required_keys = [
                "date_format", "amount_format", "column_order", 
                "credit_marker", "debit_marker", "null_marker"
            ]
            
            if not all(key in format_info for key in required_keys):
                raise ValueError("Missing required keys in format detection response")
                
            logger.info(f"Successfully detected format: {json.dumps(format_info, indent=2)}")
            return format_info
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Format detection failed: {str(e)}, using defaults")
            return {
                "date_format": "DD MMM YY",
                "amount_format": "1234.56",
                "column_order": ["date", "description", "debit", "credit", "balance"],
                "credit_marker": "separate_column",
                "debit_marker": "separate_column",
                "null_marker": ""
            }
            
    except Exception as e:
        logger.error(f"Error in format detection: {str(e)}")
        return {
            "date_format": "DD MMM YY",
            "amount_format": "1234.56",
            "column_order": ["date", "description", "debit", "credit", "balance"],
            "credit_marker": "separate_column",
            "debit_marker": "separate_column",
            "null_marker": ""
        }

def process_chunk(text: str, format_info: Dict[str, Any]) -> str:
    """Process a single chunk with improved error handling"""
    prompt = f"""
    Convert these bank transactions into CSV format using these specifications:
    - Input date format: {format_info['date_format']}
    - Input amount format: {format_info['amount_format']}
    - Column order: {format_info['column_order']}
    - Credit marker: {format_info['credit_marker']}
    - Debit marker: {format_info['debit_marker']}
    
    Convert to this format:
    - DATE as YYYY-MM-DD
    - Remove currency symbols and commas from numbers
    - Use empty string for null values
    - Output format: DATE,DESCRIPTION,DEBIT,CREDIT,BALANCE
    
    If you can't parse a transaction, skip it.
    Return only CSV data, no headers or extra text.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": "You are a financial data converter. Output only valid CSV formatted transaction data."},
                {"role": "user", "content": f"{prompt}\n\nTransactions:\n{text}"}
            ],
            temperature=0,
            max_tokens=2000
        )
        
        result = response.choices[0].message.content.strip()
        
        # Validate CSV format
        valid_lines = []
        for line in result.split('\n'):
            try:
                # Skip empty lines
                if not line.strip():
                    continue
                    
                # Validate number of columns
                parts = line.split(',')
                if len(parts) != 5:
                    logger.warning(f"Skipping invalid line (wrong number of columns): {line}")
                    continue
                
                # Basic date validation (should be YYYY-MM-DD)
                date_parts = parts[0].split('-')
                if len(date_parts) != 3 or not all(p.isdigit() for p in date_parts):
                    logger.warning(f"Skipping line with invalid date format: {line}")
                    continue
                
                valid_lines.append(line)
                
            except Exception as e:
                logger.warning(f"Error validating line: {str(e)}")
                continue
        
        time.sleep(1)  # Rate limiting
        return '\n'.join(valid_lines)
        
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        return ""

async def get_text(pdf: bytes) -> str:
    """Extract text from PDF with improved error handling"""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            pdf_path = Path(tmp) / "statement.pdf"
            txt_path = Path(tmp) / "statement.txt"
            
            pdf_path.write_bytes(pdf)
            
            try:
                subprocess.run(['ps2ascii', pdf_path, txt_path], check=True, timeout=30)
            except subprocess.TimeoutExpired:
                logger.error("PDF conversion timed out")
                raise HTTPException(status_code=500, detail="PDF conversion timed out")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error("PDF conversion failed")
                raise HTTPException(status_code=500, detail="PDF conversion failed - please ensure PDF is not encrypted")
            
            if not txt_path.exists() or txt_path.stat().st_size == 0:
                raise HTTPException(status_code=500, detail="PDF conversion produced no output")
                
            content = txt_path.read_text()
            
            # Check if we got meaningful content
            if len(content.strip()) < 100:  # Arbitrary minimum length
                raise HTTPException(status_code=500, detail="PDF conversion produced insufficient content")
                
            return content
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Statement processing error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to process statement: {str(e)}")

async def csvify(text: str) -> str:
    """Convert text to CSV with improved error handling"""
    if not text.strip():
        raise HTTPException(status_code=422, detail="Converted PDF is empty")
        
    format_info = detect_statement_format(text)
    if not format_info:
        logger.error("Could not detect statement format, using defaults")
        format_info = {
            "date_format": "MM/DD/YYYY",
            "amount_format": "1234.56",
            "column_order": ["date", "description", "debit", "credit", "balance"],
            "credit_marker": "separate_column",
            "debit_marker": "separate_column",
            "null_marker": ""
        }

    # Process in smaller chunks with overlap
    chunks = []
    chunk_size = 8000  # Reduced chunk size
    overlap = 500
    
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)
    
    logger.info(f"Processing {len(chunks)} chunks...")
    
    all_transactions = []
    seen_transactions = set()
    
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Processing chunk {i}/{len(chunks)}...")
        result = process_chunk(chunk, format_info)
        
        if result:
            for line in result.split('\n'):
                # Use first 3 fields as deduplication key
                key = ','.join(line.split(',')[:3])
                if key not in seen_transactions:
                    seen_transactions.add(key)
                    all_transactions.append(line)
    
    if not all_transactions:
        raise HTTPException(status_code=500, detail="No valid transactions found in statement")
        
    logger.info(f"Found {len(all_transactions)} total transactions")

    headers = ['DATE', 'DESCRIPTION', 'DEBIT', 'CREDIT', 'BALANCE']
    
    valid_lines = []
    for line in '\n'.join(all_transactions).split('\n'):
        if line.strip() and len(line.split(',')) == 5:
            valid_lines.append(line.strip())
    
    # with open(output_file, 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(headers)
    #     for line in valid_lines:
    #         writer.writerow(line.split(','))

    return '\n'.join(valid_lines)

def categorize_transaction(description: str) -> str:
    """Categorize a transaction with error handling"""
    categories = {
        'income': ['salary', 'deposit', 'payment received'],
        'essential': ['rent', 'utilities', 'groceries', 'insurance'],
        'discretionary': ['entertainment', 'dining', 'shopping'],
        'savings': ['investment', 'savings transfer'],
        'debt': ['loan payment', 'credit card payment'],
    }
    
    prompt = f"""
    Categorize this bank transaction into one of these categories:
    - income (salary, deposits, payments received)
    - essential (rent, utilities, groceries, insurance)
    - discretionary (entertainment, dining, shopping)
    - savings (investments, savings)
    - debt (loan payments, credit cards)

    Transaction: {description}
    
    Return only the category name, lowercase, no explanation.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        category = response.choices[0].message.content.strip().lower()
        
        # Validate category
        if category not in categories:
            logger.warning(f"Invalid category '{category}' for transaction: {description}")
            return 'other'
            
        return category
    except Exception as e:
        logger.error(f"Error categorizing transaction: {str(e)}")
        return 'other'

def score(csv: str) -> Dict[str, Any]:
    """Score transactions with improved error handling"""
    try:
        # Read CSV with explicit column names since they might be missing
        df = pd.read_csv(StringIO(csv), names=['DATE', 'DESCRIPTION', 'DEBIT', 'CREDIT', 'BALANCE'])
        
        # Clean up amount columns - handle missing values and convert to numeric
        for col in ['DEBIT', 'CREDIT', 'BALANCE']:
            # First ensure all values are strings
            df[col] = df[col].astype(str)
            # Replace empty strings with NaN
            df[col] = df[col].replace('', pd.NA)
            df[col] = df[col].replace('nan', pd.NA)
            # Clean strings and convert to numeric
            df[col] = pd.to_numeric(
                df[col].apply(lambda x: str(x).replace('$', '').replace(',', '') if pd.notna(x) else x),
                errors='coerce'
            )
            # Fill NaN with 0 for DEBIT and CREDIT
            if col in ['DEBIT', 'CREDIT']:
                df[col] = df[col].fillna(0)

        # Drop rows where all amount columns are NaN
        df = df.dropna(subset=['DEBIT', 'CREDIT', 'BALANCE'], how='all')
        
        # Ensure we have data to process
        if len(df) == 0:
            raise ValueError("No valid transactions found after cleaning")
            
        # Log data shape and column info for debugging
        logger.info(f"Processing {len(df)} transactions")
        logger.info(f"Columns present: {df.columns.tolist()}")
        
        # Add data validation logging
        logger.info(f"DEBIT column dtype: {df['DEBIT'].dtype}")
        logger.info(f"CREDIT column dtype: {df['CREDIT'].dtype}")
        logger.info(f"BALANCE column dtype: {df['BALANCE'].dtype}")
        
        # Categorize transactions
        df['category'] = df['DESCRIPTION'].apply(categorize_transaction)
        
        # Calculate metrics
        analysis = {
            'total_income': float(df[df['category'] == 'income']['CREDIT'].sum()),
            'essential_spending': float(df[df['category'] == 'essential']['DEBIT'].sum()),
            'discretionary_spending': float(df[df['category'] == 'discretionary']['DEBIT'].sum()),
            'savings_rate': float(df[df['category'] == 'savings']['CREDIT'].sum()),
            'debt_payments': float(df[df['category'] == 'debt']['DEBIT'].sum()),
            'spending_patterns': {
                'sum': {
                    category: float(group['DEBIT'].sum())
                    for category, group in df.groupby('category')
                },
                'count': {
                    category: int(len(group))
                    for category, group in df.groupby('category')
                }
            },
            'transaction_frequency': int(len(df)),
            'average_balance': float(df['BALANCE'].mean())
        }
        
        # Log successful analysis
        logger.info("Successfully completed transaction analysis")
        
        return analysis #{ 'analysis': analysis, 'assessment': 'nah' }
        
    except pd.errors.EmptyDataError:
        logger.error("Empty CSV data provided")
        raise HTTPException(status_code=422, detail="No data found in CSV")
    except ValueError as ve:
        logger.error(f"Value error in scoring: {str(ve)}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Error scoring transactions: {str(e)}")
        # Add more detailed error logging
        logger.error(f"DataFrame state at error: {df.head() if 'df' in locals() else 'DataFrame not created'}")
        raise HTTPException(status_code=500, detail=f"Error analyzing transactions: {str(e)}")
    
@app.post("/analyze-statement")
async def analyze_statement(file: UploadFile = File(...)) -> JSONResponse:
    """Analyze a PDF bank statement"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        content = await file.read()
        text = await get_text(content)
        logger.info(text)
        csv_content = await csvify(text)
        result = score(csv_content)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Statement analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)