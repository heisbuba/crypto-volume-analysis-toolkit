import re
import pandas as pd
import datetime
from dataclasses import dataclass
from typing import List, Optional
import config
from utils import SESSION, now_str

try:
    import pypdf
except:
    pypdf = None

@dataclass
class TokenData:
    ticker: str
    name: str
    market_cap: str
    volume: str
    vtmr: float
    funding: str = "-"
    oiss: str = "-"

class PDFParser:
    # UPDATED REGEX from v4.0
    FINANCIAL_PATTERN = re.compile(
        r'(\$?[+-]?[\d,\.]+[kKmMbB]?)\s+'             
        r'(\$?[+-]?[\d,\.]+[kKmMbB]?)\s+'             
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|N\/A)\s+)?' 
        r'(?:([+\-]?[\d\.\,]+\%?|[\-\–\—]|N\/A)\s+)?' 
        r'(\d*\.?\d+)'                                
    )
    IGNORE_KEYWORDS = {'page', 'coinalyze', 'contract', 'filter', 'column', 'mkt cap', 'vol 24h'}

    @classmethod
    def extract(cls, path):
        print(f"   Parsing Futures PDF: {path.name}")
        if not pypdf: return pd.DataFrame()
        data = []
        try:
            reader = pypdf.PdfReader(path)
            for page in reader.pages:
                lines = [ln.strip() for ln in (page.extract_text() or "").split("\n") if ln.strip()]
                data.extend(cls._parse_page_smart(lines))
        except Exception as e:
            print(f"   PDF Error: {e}")
            return pd.DataFrame()
        
        df = pd.DataFrame([vars(t) for t in data])
        if not df.empty:
            df['ticker'] = df['ticker'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', str(x).upper()))
        return df

    @staticmethod
    def _clean_ticker_strict(text: str) -> Optional[str]:
        if len(text) > 15:
            return None
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        if 2 <= len(cleaned) <= 12: 
            return cleaned
        return None

    @classmethod
    def _parse_page_smart(cls, lines: List[str]) -> List[TokenData]:
        financials = []
        raw_text_lines = []
        
        for line in lines:
            if any(k in line.lower() for k in cls.IGNORE_KEYWORDS):
                continue
            
            fin_match = cls.FINANCIAL_PATTERN.search(line)
            if fin_match:
                groups = fin_match.groups()
                mc = groups[0].replace('$', '').replace(',', '')
                vol = groups[1].replace('$', '').replace(',', '')
                oi_str = groups[2]       # Group 3: OI
                fund_str = groups[3]     # Group 4: Funding
                vtmr = groups[4]         # Group 5: VTMR
                
                try:
                    float(vtmr)
                    financials.append((mc, vol, vtmr, oi_str, fund_str))
                except:
                    raw_text_lines.append(line)
            else:
                if not line.isdigit() and len(line) > 1:
                    raw_text_lines.append(line)
        
        token_pairs = []
        i = 0
        while i < len(raw_text_lines):
            line = raw_text_lines[i]
            clean_current = cls._clean_ticker_strict(line)
            
            if clean_current:
                if i + 1 < len(raw_text_lines):
                    next_line = raw_text_lines[i + 1]
                    clean_next = cls._clean_ticker_strict(next_line)
                    if clean_next:
                        token_pairs.append((line, clean_next))
                        i += 2
                        continue
            
            if i + 1 < len(raw_text_lines):
                name_candidate = raw_text_lines[i]
                ticker_candidate_raw = raw_text_lines[i + 1]
                ticker = cls._clean_ticker_strict(ticker_candidate_raw)
                if ticker:
                    token_pairs.append((name_candidate, ticker))
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        tokens: List[TokenData] = []
        limit = min(len(token_pairs), len(financials))
        
        for k in range(limit):
            name, ticker = token_pairs[k]
            mc, vol, vtmr, oi_pct, fund_pct = financials[k]
            # simplified OISS/Funding string logic
            tokens.append(TokenData(
                ticker=ticker, name=name, market_cap=mc, volume=vol,
                vtmr=float(vtmr), funding=fund_pct, oiss=oi_pct
            ))
        return tokens

class DataProcessor:
    @staticmethod
    def load_spot(path):
        print(f"   Parsing Spot File: {path.name}")
        try:
            df = pd.read_html(path)[0]
            # Simple column cleanup
            df.columns = [c.lower() for c in df.columns]
            if 'ticker' not in df.columns:
                # Find ticker col
                for c in df.columns: 
                    if 'tick' in c or 'sym' in c: 
                        df.rename(columns={c:'ticker'}, inplace=True)
                        break
            if 'ticker' in df.columns:
                df['ticker'] = df['ticker'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', str(x).upper()))
            return df
        except: return pd.DataFrame()

    @staticmethod
    def generate_report(futures_df, spot_df, user_id):
        # Merge logic
        if futures_df.empty or spot_df.empty: return None
        
        merged = pd.merge(spot_df, futures_df, on='ticker', how='inner', suffixes=('_spot', '_fut'))
        
        html = f"<h1>Analysis Report for {user_id}</h1>"
        html += merged.to_html()
        
        # Footer
        html += """<div style="background:#ecf0f1;padding:15px;"><h2>OISS & Funding Cheat Sheet</h2>
        <ul><li><strong>Bullish Squeeze:</strong> OI+ Fund-</li><li><strong>Uptrend:</strong> OI+ Fund+</li></ul></div>"""
        return html

def convert_html_to_pdf(html, output_dir, user_id):
    print("   Converting to PDF...")
    pdf_path = output_dir / f"{user_id}_analysis_report.pdf"
    try:
        resp = SESSION.post(
            "https://api.html2pdf.app/v1/generate",
            json={'html': html, 'apiKey': config.HTML2PDF_API_KEY},
            headers={'Content-Type': 'application/json'}
        )
        if resp.status_code == 200:
            with open(pdf_path, "wb") as f: f.write(resp.content)
            
            # V5 Cloud Upload
            url = config.FirebaseHelper.upload_report(user_id, pdf_path)
            if url: print(f"   🚀 Cloud Backup: {url}")
            return pdf_path
    except: pass
    return None

def run_futures_analysis(user_id):
    spot_file = config.UPLOAD_FOLDER / f"{user_id}_Volumed_Spot_Tokens.html"
    futures_file = config.UPLOAD_FOLDER / f"{user_id}_futures.pdf"
    
    if not spot_file.exists() or not futures_file.exists():
        print("   ❌ Missing files. Run Spot Scan & Upload PDF first.")
        return

    f_df = PDFParser.extract(futures_file)
    s_df = DataProcessor.load_spot(spot_file)
    
    html = DataProcessor.generate_report(f_df, s_df, user_id)
    if html:
        convert_html_to_pdf(html, config.UPLOAD_FOLDER, user_id)
        print("   ✅ Analysis Complete.")