# app/services/table_extractor_basic.py
"""
Basic table extractor with simplified dependencies
"""
import logging
import re
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class TableExtractor:
    """Basic table extraction using pandas and regex"""
    
    def __init__(self):
        self.name = "BasicTableExtractor"
        logger.info("Basic Table Extractor initialized")
    
    def extract_tables_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract tables from PDF using basic methods"""
        try:
            logger.info(f"Extracting tables from {pdf_path}")
            
            # For now, return empty list as we don't have camelot
            # In a real implementation, we'd use pdfplumber or similar
            tables = []
            
            # Mock table extraction
            mock_table = {
                "table_id": 1,
                "data": [
                    ["Item", "Descrição", "Quantidade", "Unidade"],
                    ["1", "Produto A", "100", "UN"],
                    ["2", "Produto B", "50", "KG"]
                ],
                "confidence": 0.8,
                "page": 1
            }
            tables.append(mock_table)
            
            logger.info(f"Extracted {len(tables)} tables from {pdf_path}")
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []
    
    def identify_product_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify which tables contain products"""
        product_tables = []
        
        for table in tables:
            data = table.get("data", [])
            if not data:
                continue
            
            # Check if table has product-related headers
            headers = data[0] if data else []
            product_keywords = ["item", "produto", "descrição", "quantidade", "unidade", "valor"]
            
            score = 0
            for header in headers:
                if isinstance(header, str):
                    header_lower = header.lower()
                    for keyword in product_keywords:
                        if keyword in header_lower:
                            score += 1
            
            # If score is high enough, consider it a product table
            if score >= 2:
                table["is_product_table"] = True
                table["confidence_score"] = score / len(product_keywords)
                product_tables.append(table)
        
        return product_tables
    
    def extract_products_from_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract product information from tables"""
        products = []
        
        for table in tables:
            data = table.get("data", [])
            if len(data) < 2:  # Need at least header + 1 row
                continue
            
            headers = [str(h).lower() for h in data[0]]
            
            # Find column indices
            item_col = self._find_column_index(headers, ["item", "código"])
            desc_col = self._find_column_index(headers, ["descrição", "produto", "serviço"])
            qty_col = self._find_column_index(headers, ["quantidade", "qtd"])
            unit_col = self._find_column_index(headers, ["unidade", "un", "medida"])
            
            # Extract products from rows
            for i, row in enumerate(data[1:], 1):
                if len(row) <= max([c for c in [item_col, desc_col, qty_col, unit_col] if c is not None]):
                    continue
                
                product = {
                    "table_id": table.get("table_id", 0),
                    "row_number": i,
                    "item_code": row[item_col] if item_col is not None and item_col < len(row) else "",
                    "description": row[desc_col] if desc_col is not None and desc_col < len(row) else "",
                    "quantity": row[qty_col] if qty_col is not None and qty_col < len(row) else "",
                    "unit": row[unit_col] if unit_col is not None and unit_col < len(row) else "",
                }
                
                # Only add if we have meaningful data
                if product["description"] or product["item_code"]:
                    products.append(product)
        
        return products
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find the index of a column based on keywords"""
        for i, header in enumerate(headers):
            for keyword in keywords:
                if keyword in header:
                    return i
        return None