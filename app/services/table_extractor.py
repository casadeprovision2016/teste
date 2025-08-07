# app/services/table_extractor.py
"""
Advanced table extraction from PDF documents
"""
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import camelot
import tabula
import pdfplumber
import re
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

class TableExtractor:
    """Enhanced table extraction with multiple methods"""
    
    def __init__(self):
        self.extraction_methods = ['camelot', 'tabula', 'pdfplumber']
        self.table_keywords = [
            'item', 'descrição', 'quantidade', 'valor', 'preço', 'unitário',
            'total', 'produto', 'serviço', 'especificação', 'unidade',
            'marca', 'modelo', 'código', 'catmat', 'lote'
        ]
    
    def extract_tables(self, file_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF using multiple methods
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        all_tables = []
        
        # Method 1: Camelot (best for well-structured tables)
        try:
            camelot_tables = self._extract_with_camelot(str(file_path), pages)
            all_tables.extend(camelot_tables)
            logger.info(f"Camelot extracted {len(camelot_tables)} tables")
        except Exception as e:
            logger.warning(f"Camelot extraction failed: {str(e)}")
        
        # Method 2: Tabula (good for Java-based extraction)
        try:
            tabula_tables = self._extract_with_tabula(str(file_path), pages)
            all_tables.extend(tabula_tables)
            logger.info(f"Tabula extracted {len(tabula_tables)} tables")
        except Exception as e:
            logger.warning(f"Tabula extraction failed: {str(e)}")
        
        # Method 3: pdfplumber (good for text-based tables)
        try:
            plumber_tables = self._extract_with_pdfplumber(str(file_path), pages)
            all_tables.extend(plumber_tables)
            logger.info(f"pdfplumber extracted {len(plumber_tables)} tables")
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Deduplicate and merge similar tables
        unique_tables = self._deduplicate_tables(all_tables)
        
        # Clean and validate tables
        cleaned_tables = self._clean_tables(unique_tables)
        
        logger.info(f"Final extraction: {len(cleaned_tables)} unique tables")
        return cleaned_tables
    
    def _extract_with_camelot(self, file_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract tables using Camelot"""
        tables = []
        
        try:
            # Try lattice method first (better for tables with borders)
            camelot_tables = camelot.read_pdf(
                file_path,
                pages=pages or 'all',
                flavor='lattice',
                table_areas=None,
                columns=None,
                split_text=True,
                flag_size=True,
                strip_text='\n'
            )
            
            for i, table in enumerate(camelot_tables):
                if table.accuracy > 70:  # Only include high-accuracy tables
                    tables.append({
                        "id": f"camelot_lattice_{i}",
                        "method": "camelot_lattice",
                        "page": table.page,
                        "accuracy": table.accuracy,
                        "data": table.df.values.tolist(),
                        "headers": table.df.columns.tolist() if not table.df.empty else [],
                        "shape": table.shape,
                        "bbox": table.bbox,
                        "raw_table": table
                    })
            
        except Exception as e:
            logger.warning(f"Camelot lattice method failed: {str(e)}")
        
        # Try stream method if lattice didn't work well
        try:
            if len(tables) < 2:  # If lattice didn't find many tables
                camelot_tables = camelot.read_pdf(
                    file_path,
                    pages=pages or 'all',
                    flavor='stream',
                    table_areas=None,
                    columns=None,
                    edge_tol=500,
                    row_tol=10,
                    column_tol=0,
                )
                
                for i, table in enumerate(camelot_tables):
                    if table.accuracy > 50:  # Lower threshold for stream
                        tables.append({
                            "id": f"camelot_stream_{i}",
                            "method": "camelot_stream",
                            "page": table.page,
                            "accuracy": table.accuracy,
                            "data": table.df.values.tolist(),
                            "headers": table.df.columns.tolist() if not table.df.empty else [],
                            "shape": table.shape,
                            "bbox": table.bbox,
                            "raw_table": table
                        })
                        
        except Exception as e:
            logger.warning(f"Camelot stream method failed: {str(e)}")
        
        return tables
    
    def _extract_with_tabula(self, file_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract tables using Tabula"""
        tables = []
        
        try:
            # Read tables with tabula
            tabula_tables = tabula.read_pdf(
                file_path,
                pages=pages or 'all',
                multiple_tables=True,
                pandas_options={'header': 'infer'},
                lattice=True,
                stream=False,
                guess=True,
                area=None,
                columns=None
            )
            
            for i, df in enumerate(tabula_tables):
                if not df.empty and len(df.columns) > 1:
                    # Clean the dataframe
                    df = df.dropna(how='all').dropna(axis=1, how='all')
                    
                    if not df.empty:
                        tables.append({
                            "id": f"tabula_{i}",
                            "method": "tabula",
                            "page": None,  # Tabula doesn't provide page info easily
                            "accuracy": None,
                            "data": df.values.tolist(),
                            "headers": df.columns.tolist(),
                            "shape": df.shape,
                            "bbox": None,
                            "raw_table": df
                        })
            
        except Exception as e:
            logger.warning(f"Tabula extraction error: {str(e)}")
            
            # Try stream method as fallback
            try:
                tabula_tables = tabula.read_pdf(
                    file_path,
                    pages=pages or 'all',
                    multiple_tables=True,
                    pandas_options={'header': 'infer'},
                    lattice=False,
                    stream=True,
                    guess=True
                )
                
                for i, df in enumerate(tabula_tables):
                    if not df.empty and len(df.columns) > 1:
                        df = df.dropna(how='all').dropna(axis=1, how='all')
                        
                        if not df.empty:
                            tables.append({
                                "id": f"tabula_stream_{i}",
                                "method": "tabula_stream",
                                "page": None,
                                "accuracy": None,
                                "data": df.values.tolist(),
                                "headers": df.columns.tolist(),
                                "shape": df.shape,
                                "bbox": None,
                                "raw_table": df
                            })
                            
            except Exception as e2:
                logger.warning(f"Tabula stream method also failed: {str(e2)}")
        
        return tables
    
    def _extract_with_pdfplumber(self, file_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract tables using pdfplumber"""
        tables = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                page_numbers = self._parse_page_range(pages, len(pdf.pages))
                
                for page_num in page_numbers:
                    page = pdf.pages[page_num - 1]  # 0-indexed
                    
                    # Extract tables from page
                    page_tables = page.extract_tables()
                    
                    for i, table_data in enumerate(page_tables):
                        if table_data and len(table_data) > 1:  # At least header + 1 row
                            # Convert to consistent format
                            headers = table_data[0] if table_data[0] else []
                            data_rows = table_data[1:] if len(table_data) > 1 else []
                            
                            # Clean empty cells
                            cleaned_data = []
                            for row in data_rows:
                                cleaned_row = [cell.strip() if cell else "" for cell in row]
                                if any(cleaned_row):  # Skip completely empty rows
                                    cleaned_data.append(cleaned_row)
                            
                            if cleaned_data:
                                tables.append({
                                    "id": f"pdfplumber_page_{page_num}_table_{i}",
                                    "method": "pdfplumber",
                                    "page": page_num,
                                    "accuracy": None,
                                    "data": cleaned_data,
                                    "headers": [h.strip() if h else "" for h in headers],
                                    "shape": (len(cleaned_data), len(headers)),
                                    "bbox": None,
                                    "raw_table": table_data
                                })
                                
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        return tables
    
    def identify_product_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify which tables contain products/services information
        """
        product_tables = []
        
        for table in tables:
            score = self._calculate_product_table_score(table)
            
            if score > 0.3:  # Threshold for product table identification
                table["product_score"] = score
                table["is_product_table"] = True
                table["table_type"] = "products"
                
                # Enhanced product table processing
                enhanced_table = self._enhance_product_table(table)
                product_tables.append(enhanced_table)
            else:
                table["product_score"] = score
                table["is_product_table"] = False
                table["table_type"] = self._classify_table_type(table)
        
        # Sort by product score
        product_tables.sort(key=lambda x: x.get("product_score", 0), reverse=True)
        
        logger.info(f"Identified {len(product_tables)} product tables out of {len(tables)} total")
        return product_tables
    
    def _calculate_product_table_score(self, table: Dict[str, Any]) -> float:
        """Calculate how likely a table is to contain product information"""
        score = 0.0
        headers = [str(h).lower() for h in table.get("headers", [])]
        data = table.get("data", [])
        
        # Check headers for product-related keywords
        header_score = 0
        for header in headers:
            for keyword in self.table_keywords:
                if keyword in header:
                    header_score += 1
        
        if headers:
            score += min(header_score / len(headers), 1.0) * 0.4
        
        # Check data patterns
        if data and len(data) > 0:
            # Look for numeric values (prices, quantities)
            numeric_columns = 0
            for col_idx in range(len(data[0]) if data[0] else 0):
                numeric_count = 0
                for row in data[:10]:  # Check first 10 rows
                    if col_idx < len(row) and row[col_idx]:
                        cell = str(row[col_idx]).strip()
                        if self._is_numeric_value(cell):
                            numeric_count += 1
                
                if numeric_count > len(data[:10]) * 0.3:  # 30% numeric
                    numeric_columns += 1
            
            if len(data[0]) > 0:
                score += min(numeric_columns / len(data[0]), 0.5) * 0.3
        
        # Bonus for minimum table size
        if len(data) >= 3 and len(table.get("headers", [])) >= 3:
            score += 0.2
        
        # Bonus for accuracy (if available from Camelot)
        if table.get("accuracy"):
            score += min(table["accuracy"] / 100, 0.1)
        
        return min(score, 1.0)
    
    def _enhance_product_table(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance product table with structured data extraction"""
        enhanced = table.copy()
        headers = table.get("headers", [])
        data = table.get("data", [])
        
        # Map headers to standard fields
        header_mapping = self._map_headers_to_fields(headers)
        enhanced["header_mapping"] = header_mapping
        
        # Extract structured products
        products = []
        for row_idx, row in enumerate(data):
            if len(row) > 0 and any(str(cell).strip() for cell in row):
                product = self._extract_product_from_row(row, headers, header_mapping)
                if product:
                    product["row_index"] = row_idx
                    products.append(product)
        
        enhanced["products"] = products
        enhanced["product_count"] = len(products)
        
        # Calculate table statistics
        enhanced["statistics"] = self._calculate_table_statistics(products)
        
        return enhanced
    
    def _map_headers_to_fields(self, headers: List[str]) -> Dict[str, str]:
        """Map table headers to standard product fields"""
        mapping = {}
        
        field_patterns = {
            "item": ["item", "seq", "ordem", "número", "nº", "n°"],
            "description": ["descrição", "especificação", "objeto", "produto", "serviço", "descricao"],
            "quantity": ["qtd", "quantidade", "qtde", "quant", "qnt"],
            "unit": ["unid", "unidade", "un", "medida", "und"],
            "unit_price": ["unitário", "preço unit", "valor unit", "preço unitario", "vl unit", "unit"],
            "total_price": ["total", "valor total", "preço total", "vl total", "subtotal"],
            "brand": ["marca", "fabricante"],
            "model": ["modelo", "referência", "ref"],
            "code": ["código", "catmat", "código catmat", "cod"]
        }
        
        for i, header in enumerate(headers):
            header_lower = str(header).lower().strip()
            
            for field, patterns in field_patterns.items():
                for pattern in patterns:
                    if pattern in header_lower:
                        mapping[field] = i
                        break
                
                if field in mapping:
                    break
        
        return mapping
    
    def _extract_product_from_row(self, row: List, headers: List[str], mapping: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Extract product information from table row"""
        product = {}
        
        # Extract mapped fields
        for field, col_idx in mapping.items():
            if col_idx < len(row) and row[col_idx]:
                value = str(row[col_idx]).strip()
                
                if field in ["quantity", "unit_price", "total_price"]:
                    # Parse numeric values
                    numeric_value = self._parse_numeric_value(value)
                    product[field] = numeric_value
                else:
                    product[field] = value
        
        # Extract unmapped fields
        unmapped_data = {}
        for i, cell in enumerate(row):
            if i not in mapping.values() and cell:
                header_name = headers[i] if i < len(headers) else f"column_{i}"
                unmapped_data[str(header_name)] = str(cell).strip()
        
        if unmapped_data:
            product["additional_data"] = unmapped_data
        
        # Only return if we have meaningful data
        if any(product.get(field) for field in ["description", "item", "code"]):
            return product
        
        return None
    
    def _parse_numeric_value(self, value: str) -> Optional[float]:
        """Parse numeric value from string"""
        if not value:
            return None
        
        # Remove common currency symbols and formatting
        cleaned = str(value).strip()
        cleaned = re.sub(r'[R$\s]', '', cleaned)
        cleaned = cleaned.replace('.', '')  # Remove thousands separator
        cleaned = cleaned.replace(',', '.')  # Use dot as decimal separator
        
        try:
            return float(cleaned)
        except ValueError:
            # Try to extract first number found
            numbers = re.findall(r'\d+[.,]?\d*', cleaned)
            if numbers:
                try:
                    return float(numbers[0].replace(',', '.'))
                except ValueError:
                    pass
        
        return None
    
    def _is_numeric_value(self, value: str) -> bool:
        """Check if string represents a numeric value"""
        return self._parse_numeric_value(value) is not None
    
    def _classify_table_type(self, table: Dict[str, Any]) -> str:
        """Classify table type based on content"""
        headers = [str(h).lower() for h in table.get("headers", [])]
        
        # Classification keywords
        type_keywords = {
            "schedule": ["cronograma", "prazo", "data", "período"],
            "budget": ["orçamento", "custo", "estimativa"],
            "requirements": ["requisito", "critério", "exigência"],
            "contacts": ["contato", "telefone", "email", "endereço"],
            "documents": ["documento", "certidão", "comprovante"],
            "other": []
        }
        
        for table_type, keywords in type_keywords.items():
            if table_type == "other":
                continue
            
            for keyword in keywords:
                if any(keyword in header for header in headers):
                    return table_type
        
        return "other"
    
    def _calculate_table_statistics(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for product table"""
        if not products:
            return {}
        
        stats = {
            "total_items": len(products),
            "has_quantities": 0,
            "has_prices": 0,
            "total_quantity": 0,
            "total_value": 0,
            "average_unit_price": 0,
            "price_range": {"min": None, "max": None}
        }
        
        unit_prices = []
        
        for product in products:
            if product.get("quantity"):
                stats["has_quantities"] += 1
                stats["total_quantity"] += product["quantity"]
            
            if product.get("unit_price"):
                stats["has_prices"] += 1
                unit_prices.append(product["unit_price"])
            
            if product.get("total_price"):
                stats["total_value"] += product["total_price"]
        
        if unit_prices:
            stats["average_unit_price"] = sum(unit_prices) / len(unit_prices)
            stats["price_range"]["min"] = min(unit_prices)
            stats["price_range"]["max"] = max(unit_prices)
        
        return stats
    
    def _deduplicate_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate tables from different extraction methods"""
        if len(tables) <= 1:
            return tables
        
        unique_tables = []
        
        for table in tables:
            is_duplicate = False
            
            for existing in unique_tables:
                similarity = self._calculate_table_similarity(table, existing)
                
                if similarity > 0.8:  # High similarity threshold
                    is_duplicate = True
                    
                    # Keep the one with higher accuracy or from preferred method
                    if self._is_better_table(table, existing):
                        # Replace existing with current
                        unique_tables.remove(existing)
                        unique_tables.append(table)
                    break
            
            if not is_duplicate:
                unique_tables.append(table)
        
        return unique_tables
    
    def _calculate_table_similarity(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> float:
        """Calculate similarity between two tables"""
        # Compare dimensions
        shape1 = table1.get("shape", (0, 0))
        shape2 = table2.get("shape", (0, 0))
        
        if shape1 != shape2:
            return 0.0
        
        # Compare headers
        headers1 = table1.get("headers", [])
        headers2 = table2.get("headers", [])
        
        header_similarity = 0.0
        if headers1 and headers2 and len(headers1) == len(headers2):
            matches = sum(1 for h1, h2 in zip(headers1, headers2) 
                         if str(h1).lower().strip() == str(h2).lower().strip())
            header_similarity = matches / len(headers1)
        
        # Compare first few rows of data
        data1 = table1.get("data", [])[:3]
        data2 = table2.get("data", [])[:3]
        
        data_similarity = 0.0
        if data1 and data2:
            total_cells = 0
            matching_cells = 0
            
            for row1, row2 in zip(data1, data2):
                for cell1, cell2 in zip(row1, row2):
                    total_cells += 1
                    if str(cell1).strip() == str(cell2).strip():
                        matching_cells += 1
            
            if total_cells > 0:
                data_similarity = matching_cells / total_cells
        
        # Weighted average
        return (header_similarity * 0.4) + (data_similarity * 0.6)
    
    def _is_better_table(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> bool:
        """Determine which table is better quality"""
        # Prefer tables with accuracy scores
        acc1 = table1.get("accuracy", 0) or 0
        acc2 = table2.get("accuracy", 0) or 0
        
        if acc1 != acc2:
            return acc1 > acc2
        
        # Prefer certain extraction methods
        method_priority = {"camelot_lattice": 3, "camelot_stream": 2, "tabula": 1, "pdfplumber": 1}
        
        priority1 = method_priority.get(table1.get("method", ""), 0)
        priority2 = method_priority.get(table2.get("method", ""), 0)
        
        return priority1 > priority2
    
    def _clean_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and validate extracted tables"""
        cleaned = []
        
        for table in tables:
            # Skip very small tables
            if table.get("shape", (0, 0))[0] < 2:
                continue
            
            # Clean data
            cleaned_data = []
            for row in table.get("data", []):
                cleaned_row = []
                for cell in row:
                    if cell is not None:
                        cleaned_cell = str(cell).strip()
                        # Remove excessive whitespace
                        cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell)
                        cleaned_row.append(cleaned_cell)
                    else:
                        cleaned_row.append("")
                
                # Skip completely empty rows
                if any(cleaned_row):
                    cleaned_data.append(cleaned_row)
            
            if cleaned_data:
                table["data"] = cleaned_data
                table["shape"] = (len(cleaned_data), len(cleaned_data[0]) if cleaned_data else 0)
                cleaned.append(table)
        
        return cleaned
    
    def _parse_page_range(self, pages: Optional[str], total_pages: int) -> List[int]:
        """Parse page range string into list of page numbers"""
        if not pages or pages == 'all':
            return list(range(1, total_pages + 1))
        
        page_numbers = []
        
        for part in pages.split(','):
            part = part.strip()
            
            if '-' in part:
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                page_numbers.extend(range(start, end + 1))
            else:
                page_numbers.append(int(part))
        
        # Filter valid pages
        return [p for p in page_numbers if 1 <= p <= total_pages]