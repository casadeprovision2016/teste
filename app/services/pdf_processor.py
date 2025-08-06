# app/services/pdf_processor.py
"""
PDF processing utilities for text and metadata extraction
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class PDFProcessor:
    """Enhanced PDF processor with multiple extraction methods"""
    
    def __init__(self):
        self.supported_formats = ['.pdf']
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from PDF using multiple methods for best results
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        text = ""
        
        # Method 1: Try PyMuPDF (fitz) - best for complex layouts
        try:
            text = self._extract_with_fitz(str(file_path))
            if len(text.strip()) > 100:  # If we got substantial text
                logger.info(f"Successfully extracted text with PyMuPDF: {len(text)} chars")
                return text
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}")
        
        # Method 2: Try pdfplumber - good for tables and structured content
        try:
            text = self._extract_with_pdfplumber(str(file_path))
            if len(text.strip()) > 100:
                logger.info(f"Successfully extracted text with pdfplumber: {len(text)} chars")
                return text
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Method 3: Fallback to PyPDF2 - basic extraction
        try:
            text = self._extract_with_pypdf2(str(file_path))
            logger.info(f"Successfully extracted text with PyPDF2: {len(text)} chars")
            return text
        except Exception as e:
            logger.error(f"All PDF extraction methods failed: {str(e)}")
            raise
    
    def _extract_with_fitz(self, file_path: str) -> str:
        """Extract text using PyMuPDF"""
        doc = fitz.open(file_path)
        text_parts = []
        
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text()
            
            if text.strip():
                text_parts.append(f"--- Página {page_num + 1} ---\n{text}")
        
        doc.close()
        return "\n\n".join(text_parts)
    
    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """Extract text using pdfplumber"""
        text_parts = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                
                if text and text.strip():
                    text_parts.append(f"--- Página {page_num + 1} ---\n{text}")
        
        return "\n\n".join(text_parts)
    
    def _extract_with_pypdf2(self, file_path: str) -> str:
        """Extract text using PyPDF2"""
        text_parts = []
        
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                
                if text and text.strip():
                    text_parts.append(f"--- Página {page_num + 1} ---\n{text}")
        
        return "\n\n".join(text_parts)
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF
        """
        file_path = Path(file_path)
        metadata = {
            "filename": file_path.name,
            "file_size": file_path.stat().st_size,
            "created_at": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
            "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            "pages": 0,
            "title": "",
            "author": "",
            "subject": "",
            "creator": "",
            "producer": "",
            "creation_date": "",
            "modification_date": "",
            "encrypted": False,
            "pdf_version": ""
        }
        
        try:
            # Use PyMuPDF to extract detailed metadata
            doc = fitz.open(str(file_path))
            
            metadata["pages"] = doc.page_count
            metadata["encrypted"] = doc.needs_pass
            
            # Extract PDF metadata
            pdf_metadata = doc.metadata
            if pdf_metadata:
                metadata.update({
                    "title": pdf_metadata.get("title", ""),
                    "author": pdf_metadata.get("author", ""),
                    "subject": pdf_metadata.get("subject", ""),
                    "creator": pdf_metadata.get("creator", ""),
                    "producer": pdf_metadata.get("producer", ""),
                    "creation_date": pdf_metadata.get("creationDate", ""),
                    "modification_date": pdf_metadata.get("modDate", ""),
                    "pdf_version": doc.pdf_version()
                })
            
            doc.close()
            
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata with PyMuPDF: {str(e)}")
            
            # Fallback to PyPDF2
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    metadata["pages"] = len(pdf_reader.pages)
                    metadata["encrypted"] = pdf_reader.is_encrypted
                    
                    if pdf_reader.metadata:
                        metadata.update({
                            "title": str(pdf_reader.metadata.get("/Title", "")),
                            "author": str(pdf_reader.metadata.get("/Author", "")),
                            "subject": str(pdf_reader.metadata.get("/Subject", "")),
                            "creator": str(pdf_reader.metadata.get("/Creator", "")),
                            "producer": str(pdf_reader.metadata.get("/Producer", "")),
                            "creation_date": str(pdf_reader.metadata.get("/CreationDate", "")),
                            "modification_date": str(pdf_reader.metadata.get("/ModDate", ""))
                        })
                        
            except Exception as e2:
                logger.error(f"Failed to extract metadata with PyPDF2: {str(e2)}")
        
        return metadata
    
    def extract_images(self, file_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        Extract images from PDF
        """
        if not output_dir:
            output_dir = Path(file_path).parent / "extracted_images"
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_paths = []
        
        try:
            doc = fitz.open(file_path)
            
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # Skip if not RGB or GRAY
                        img_path = output_dir / f"page_{page_num + 1}_img_{img_index + 1}.png"
                        pix.save(str(img_path))
                        image_paths.append(str(img_path))
                    
                    pix = None
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Failed to extract images: {str(e)}")
        
        return image_paths
    
    def get_page_text(self, file_path: str, page_number: int) -> str:
        """
        Extract text from specific page
        """
        try:
            doc = fitz.open(file_path)
            
            if page_number < 1 or page_number > doc.page_count:
                raise ValueError(f"Page {page_number} out of range (1-{doc.page_count})")
            
            page = doc.load_page(page_number - 1)  # 0-indexed
            text = page.get_text()
            doc.close()
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to extract page {page_number}: {str(e)}")
            return ""
    
    def search_text(self, file_path: str, search_term: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search for text in PDF and return matches with page numbers
        """
        matches = []
        
        try:
            doc = fitz.open(file_path)
            
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                # Search for term
                if case_sensitive:
                    found_positions = [(m.start(), m.end()) for m in re.finditer(re.escape(search_term), text)]
                else:
                    found_positions = [(m.start(), m.end()) for m in re.finditer(re.escape(search_term), text, re.IGNORECASE)]
                
                for start, end in found_positions:
                    # Get context around the match
                    context_start = max(0, start - 100)
                    context_end = min(len(text), end + 100)
                    context = text[context_start:context_end].strip()
                    
                    matches.append({
                        "page": page_num + 1,
                        "position": (start, end),
                        "context": context,
                        "match": text[start:end]
                    })
            
            doc.close()
            
        except Exception as e:
            logger.error(f"Failed to search text: {str(e)}")
        
        return matches
    
    def validate_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Validate PDF file and return validation results
        """
        validation = {
            "is_valid": False,
            "is_readable": False,
            "is_encrypted": False,
            "page_count": 0,
            "file_size": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                validation["errors"].append("File does not exist")
                return validation
            
            validation["file_size"] = file_path.stat().st_size
            
            # Check if file is too small
            if validation["file_size"] < 1024:  # Less than 1KB
                validation["warnings"].append("File size is very small")
            
            # Check if file is too large
            if validation["file_size"] > 100 * 1024 * 1024:  # Larger than 100MB
                validation["warnings"].append("File size is very large")
            
            # Try to open and validate PDF
            doc = fitz.open(str(file_path))
            
            validation["is_valid"] = True
            validation["page_count"] = doc.page_count
            validation["is_encrypted"] = doc.needs_pass
            
            if doc.needs_pass:
                validation["warnings"].append("PDF is password protected")
            else:
                # Try to read first page to check readability
                if doc.page_count > 0:
                    try:
                        page = doc.load_page(0)
                        text = page.get_text()
                        validation["is_readable"] = len(text.strip()) > 0
                        
                        if not validation["is_readable"]:
                            validation["warnings"].append("PDF appears to be image-based or has no extractable text")
                    except Exception as e:
                        validation["errors"].append(f"Failed to read content: {str(e)}")
                else:
                    validation["errors"].append("PDF has no pages")
            
            doc.close()
            
        except Exception as e:
            validation["errors"].append(f"Failed to validate PDF: {str(e)}")
        
        return validation