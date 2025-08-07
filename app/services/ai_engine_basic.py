# app/services/ai_engine_basic.py
"""
Basic AI engine with simplified dependencies for initial deployment
"""
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import re
from datetime import datetime
import hashlib

import ollama

logger = logging.getLogger(__name__)

class BasicTextSplitter:
    """Simple text splitter without langchain dependency"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Find a good breaking point (sentence end)
            if end < len(text):
                for i in range(min(100, end - start)):
                    if text[end - i] in '.!?':
                        end = end - i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            if start >= len(text):
                break
                
        return chunks

class BasicProcessor:
    """Basic document processor without heavy dependencies"""
    
    def __init__(self):
        self.name = "BasicProcessor"
    
    async def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Basic PDF processing placeholder"""
        return {
            "text": f"Processed content from {pdf_path}",
            "metadata": {"processor": "basic", "pages": 1}
        }

class LlamaProcessor:
    """Processador Llama para análise de texto"""
    
    def __init__(self, model_name: str = "llama3.2:3b", host: str = "http://ollama:11434"):
        self.model_name = model_name
        self.host = host
        self.client = ollama.Client(host=host)
        
        # Cache para resultados
        self.cache = {}
        
        logger.info(f"Llama processor initialized with model: {model_name}")
    
    def _get_cache_key(self, text: str, analysis_type: str) -> str:
        """Generate cache key for analysis results"""
        content = f"{analysis_type}:{text}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def analyze_text(self, text: str, analysis_type: str = "general") -> Dict[str, Any]:
        """Analyze text using Llama model"""
        cache_key = self._get_cache_key(text, analysis_type)
        
        if cache_key in self.cache:
            logger.debug(f"Cache hit for {analysis_type} analysis")
            return self.cache[cache_key]
        
        try:
            prompt = self._get_prompt(analysis_type, text)
            
            response = await asyncio.to_thread(
                self.client.chat,
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            result = self._parse_response(response, analysis_type)
            self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error in Llama analysis: {e}")
            return {"error": str(e), "analysis_type": analysis_type}
    
    def _get_prompt(self, analysis_type: str, text: str) -> str:
        """Get prompt for different analysis types"""
        prompts = {
            "general": f"""
            Analise o seguinte texto de edital público brasileiro:
            
            {text}
            
            Forneça uma análise estruturada incluindo:
            1. Tipo de licitação
            2. Objeto principal
            3. Valor estimado (se mencionado)
            4. Prazo de execução
            5. Requisitos principais
            
            Responda em formato JSON válido.
            """,
            
            "products": f"""
            Do seguinte texto de edital, extraia TODOS os produtos/serviços mencionados:
            
            {text}
            
            Para cada produto, identifique:
            - Nome/descrição
            - Quantidade (se especificada)
            - Unidade de medida
            - Especificações técnicas
            
            Responda em formato JSON válido.
            """,
            
            "risks": f"""
            Analise os seguintes riscos no texto do edital:
            
            {text}
            
            Identifique:
            1. Riscos técnicos
            2. Riscos financeiros
            3. Riscos de cronograma
            4. Riscos regulatórios
            5. Nível de risco geral (alto/médio/baixo)
            
            Responda em formato JSON válido.
            """
        }
        
        return prompts.get(analysis_type, prompts["general"])
    
    def _parse_response(self, response: Dict[str, Any], analysis_type: str) -> Dict[str, Any]:
        """Parse Llama response"""
        try:
            content = response.get("message", {}).get("content", "")
            
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            # Fallback to structured text
            return {
                "raw_response": content,
                "analysis_type": analysis_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except json.JSONDecodeError:
            return {
                "raw_response": response.get("message", {}).get("content", ""),
                "analysis_type": analysis_type,
                "parse_error": True,
                "timestamp": datetime.utcnow().isoformat()
            }

class AIEngine:
    """Main AI Engine with basic functionality"""
    
    def __init__(self):
        from app.core.config import settings
        self.processor = BasicProcessor()
        self.llama = LlamaProcessor(
            model_name=settings.MODEL_NAME,
            host=settings.OLLAMA_HOST
        )
        self.text_splitter = BasicTextSplitter()
        
        logger.info("Basic AI Engine initialized successfully")
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process document with basic AI analysis"""
        try:
            logger.info(f"Processing document: {file_path}")
            
            # Basic document processing
            doc_result = await self.processor.process_pdf(file_path)
            text_content = doc_result.get("text", "")
            
            # Split text for analysis
            chunks = self.text_splitter.split_text(text_content)
            
            # Analyze with Llama
            analyses = []
            for i, chunk in enumerate(chunks[:3]):  # Limit to first 3 chunks
                analysis = await self.llama.analyze_text(chunk, "general")
                analyses.append({
                    "chunk_id": i,
                    "analysis": analysis
                })
            
            result = {
                "document_path": file_path,
                "processing_timestamp": datetime.utcnow().isoformat(),
                "processor": "basic",
                "text_length": len(text_content),
                "chunks_analyzed": len(analyses),
                "analyses": analyses,
                "metadata": doc_result.get("metadata", {})
            }
            
            logger.info(f"Document processing completed: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {e}")
            return {
                "document_path": file_path,
                "error": str(e),
                "processing_timestamp": datetime.utcnow().isoformat()
            }
    
    async def extract_products(self, text: str) -> List[Dict[str, Any]]:
        """Extract products from text"""
        try:
            chunks = self.text_splitter.split_text(text)
            all_products = []
            
            for chunk in chunks:
                analysis = await self.llama.analyze_text(chunk, "products")
                if "products" in analysis:
                    all_products.extend(analysis["products"])
            
            return all_products
            
        except Exception as e:
            logger.error(f"Error extracting products: {e}")
            return []
    
    async def analyze_risks(self, text: str) -> Dict[str, Any]:
        """Analyze risks in the text"""
        try:
            chunks = self.text_splitter.split_text(text)
            risk_analysis = await self.llama.analyze_text(chunks[0] if chunks else text, "risks")
            
            return risk_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing risks: {e}")
            return {"error": str(e)}