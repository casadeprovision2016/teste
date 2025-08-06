# app/services/ai_engine.py
"""
Motor de IA integrando Docling para extração e Llama para análise
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
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import Ollama
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat, OutputFormat
from docling.datamodel.pipeline_options import PipelineOptions
from docling.datamodel.document import Document

logger = logging.getLogger(__name__)

class DoclingProcessor:
    """Processador de documentos usando IBM Docling"""
    
    def __init__(self):
        self.converter = DocumentConverter()
        self.cache_dir = Path("/app/cache/docling")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Processa documento com Docling para extração estruturada
        """
        # Check cache first
        cache_key = self._get_cache_key(file_path)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f"Using cached Docling result for {file_path}")
            return cached_result
        
        # Configure pipeline options
        pipeline_options = PipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            table_structure_options={
                "mode": "accurate",  # or "fast"
                "detect_borderless": True,
                "refine_columns": True
            },
            ocr_options={
                "lang": ["por", "eng"],
                "dpi": 300
            }
        )
        
        # Convert document
        logger.info(f"Processing document with Docling: {file_path}")
        result = self.converter.convert(
            file_path,
            input_format=InputFormat.PDF,
            output_format=OutputFormat.JSON,
            pipeline_options=pipeline_options
        )
        
        # Parse result
        parsed_result = self._parse_docling_result(result)
        
        # Cache result
        self._cache_result(cache_key, parsed_result)
        
        return parsed_result
    
    def _parse_docling_result(self, result: Document) -> Dict[str, Any]:
        """Parse Docling result into structured format"""
        parsed = {
            "text": "",
            "tables": [],
            "sections": {},
            "metadata": {},
            "images": [],
            "layout": []
        }
        
        # Extract text content
        if hasattr(result, 'text'):
            parsed["text"] = result.text
        
        # Extract tables
        if hasattr(result, 'tables'):
            for table in result.tables:
                parsed_table = {
                    "id": table.id,
                    "headers": table.headers if hasattr(table, 'headers') else [],
                    "data": self._parse_table_data(table),
                    "caption": table.caption if hasattr(table, 'caption') else None,
                    "page": table.page_number if hasattr(table, 'page_number') else None
                }
                parsed["tables"].append(parsed_table)
        
        # Extract sections
        if hasattr(result, 'sections'):
            for section in result.sections:
                section_name = section.title if hasattr(section, 'title') else f"section_{section.id}"
                parsed["sections"][section_name] = {
                    "text": section.text if hasattr(section, 'text') else "",
                    "level": section.level if hasattr(section, 'level') else 0
                }
        
        # Extract metadata
        if hasattr(result, 'metadata'):
            parsed["metadata"] = {
                "title": result.metadata.title if hasattr(result.metadata, 'title') else None,
                "author": result.metadata.author if hasattr(result.metadata, 'author') else None,
                "pages": result.metadata.pages if hasattr(result.metadata, 'pages') else None,
                "creation_date": result.metadata.creation_date if hasattr(result.metadata, 'creation_date') else None
            }
        
        # Extract layout information
        if hasattr(result, 'layout'):
            for element in result.layout:
                parsed["layout"].append({
                    "type": element.type,
                    "bbox": element.bbox if hasattr(element, 'bbox') else None,
                    "page": element.page if hasattr(element, 'page') else None,
                    "confidence": element.confidence if hasattr(element, 'confidence') else None
                })
        
        return parsed
    
    def _parse_table_data(self, table) -> List[List[str]]:
        """Parse table data into 2D list"""
        data = []
        if hasattr(table, 'rows'):
            for row in table.rows:
                row_data = []
                if hasattr(row, 'cells'):
                    for cell in row.cells:
                        cell_text = cell.text if hasattr(cell, 'text') else ""
                        row_data.append(cell_text)
                data.append(row_data)
        return data
    
    def _get_cache_key(self, file_path: str) -> str:
        """Generate cache key for file"""
        file_stat = Path(file_path).stat()
        hash_input = f"{file_path}_{file_stat.st_size}_{file_stat.st_mtime}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if exists"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache processing result"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

class LlamaAnalyzer:
    """Analisador usando Llama via Ollama"""
    
    def __init__(self, model_name: str = "llama3.2:3b"):
        self.model_name = model_name
        self.client = ollama.Client(host="http://ollama:11434")
        self.llm = Ollama(model=model_name, base_url="http://ollama:11434")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        # Ensure model is pulled
        self._ensure_model()
    
    def _ensure_model(self):
        """Ensure Llama model is available"""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            
            if self.model_name not in model_names:
                logger.info(f"Pulling model {self.model_name}...")
                self.client.pull(self.model_name)
                logger.info(f"Model {self.model_name} pulled successfully")
        except Exception as e:
            logger.error(f"Error ensuring model: {str(e)}")
    
    async def analyze_edital(self, 
                            text: str, 
                            tables: List[Dict], 
                            metadata: Dict) -> Dict[str, Any]:
        """
        Analisa edital usando Llama
        """
        # Split text if too long
        chunks = self.text_splitter.split_text(text) if len(text) > 4000 else [text]
        
        # Analyze each chunk
        chunk_analyses = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Analyzing chunk {i+1}/{len(chunks)}")
            analysis = await self._analyze_chunk(chunk, tables, metadata)
            chunk_analyses.append(analysis)
        
        # Combine analyses
        combined_analysis = self._combine_analyses(chunk_analyses)
        
        # Final refinement
        refined_analysis = await self._refine_analysis(combined_analysis, text, tables)
        
        return refined_analysis
    
    async def _analyze_chunk(self, 
                            chunk: str, 
                            tables: List[Dict], 
                            metadata: Dict) -> Dict[str, Any]:
        """Analyze a text chunk"""
        
        prompt = f"""
        Você é um especialista em análise de editais de licitação do governo brasileiro.
        Analise o seguinte trecho de edital e extraia informações estruturadas.
        
        TEXTO DO EDITAL:
        {chunk}
        
        TABELAS ENCONTRADAS: {len(tables)} tabelas
        
        METADADOS:
        - UASG: {metadata.get('uasg', 'Não informado')}
        - Ano: {metadata.get('ano', 'Não informado')}
        - Número: {metadata.get('numero_pregao', 'Não informado')}
        
        EXTRAIA AS SEGUINTES INFORMAÇÕES (retorne em formato JSON):
        1. numero_pregao: Número do pregão
        2. uasg: Código UASG
        3. orgao: Nome do órgão
        4. objeto: Descrição detalhada do objeto
        5. valor_estimado: Valor estimado total (número)
        6. data_abertura: Data de abertura (formato: DD/MM/YYYY HH:MM)
        7. modalidade: Modalidade da licitação
        8. tipo_licitacao: Tipo (menor preço, técnica e preço, etc)
        9. criterio_julgamento: Critério de julgamento
        10. prazo_entrega: Prazo de entrega
        11. local_entrega: Local de entrega
        12. condicoes_pagamento: Condições de pagamento
        13. requisitos_tecnicos: Lista de requisitos técnicos principais
        14. documentos_habilitacao: Lista de documentos necessários
        15. observacoes_importantes: Observações e alertas importantes
        
        Responda APENAS com o JSON estruturado, sem explicações adicionais.
        """
        
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 2048
                }
            )
            
            # Parse JSON response
            result_text = response['response']
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON from Llama response")
                    return {}
            
            return {}
            
        except Exception as e:
            logger.error(f"Error in chunk analysis: {str(e)}")
            return {}
    
    async def extract_products(self, tables: List[Dict]) -> List[Dict]:
        """
        Extrai e estrutura produtos das tabelas
        """
        products = []
        
        for table in tables:
            if self._is_product_table(table):
                prompt = f"""
                Analise a seguinte tabela de produtos de um edital e estruture os dados.
                
                CABEÇALHOS: {table.get('headers', [])}
                
                DADOS (primeiras 5 linhas):
                {table.get('data', [])[:5]}
                
                Para cada produto, extraia:
                1. item: Número do item
                2. descricao: Descrição completa
                3. quantidade: Quantidade (número)
                4. unidade: Unidade de medida
                5. valor_unitario: Valor unitário (número)
                6. valor_total: Valor total (número)
                7. especificacoes: Especificações técnicas adicionais
                
                Retorne uma lista JSON de produtos estruturados.
                """
                
                try:
                    response = self.client.generate(
                        model=self.model_name,
                        prompt=prompt,
                        stream=False,
                        options={"temperature": 0.1}
                    )
                    
                    result_text = response['response']
                    json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                    
                    if json_match:
                        try:
                            table_products = json.loads(json_match.group())
                            products.extend(table_products)
                        except json.JSONDecodeError:
                            logger.error("Failed to parse products JSON")
                            
                except Exception as e:
                    logger.error(f"Error extracting products: {str(e)}")
        
        return products
    
    async def analyze_risks(self, 
                          text: str, 
                          structured_data: Dict,
                          products: List[Dict]) -> List[Dict]:
        """
        Analisa riscos do edital
        """
        prompt = f"""
        Como especialista em licitações, identifique os principais RISCOS neste edital.
        
        OBJETO: {structured_data.get('objeto', 'Não identificado')}
        VALOR: R$ {structured_data.get('valor_estimado', 0):,.2f}
        PRAZO: {structured_data.get('prazo_entrega', 'Não especificado')}
        PRODUTOS: {len(products)} itens
        
        TRECHO DO EDITAL:
        {text[:3000]}
        
        Identifique riscos nas seguintes categorias:
        1. TÉCNICOS: Complexidade, especificações, compatibilidade
        2. LEGAIS: Conformidade, documentação, penalidades
        3. COMERCIAIS: Preços, margens, concorrência
        4. OPERACIONAIS: Prazos, logística, capacidade
        
        Para cada risco, forneça:
        - tipo: Categoria do risco
        - titulo: Título descritivo
        - descricao: Descrição detalhada
        - probabilidade: Alta, Média ou Baixa
        - impacto: Alto, Médio ou Baixo
        - mitigacao: Estratégia de mitigação sugerida
        
        Retorne uma lista JSON de riscos.
        """
        
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.3}
            )
            
            result_text = response['response']
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            
            if json_match:
                try:
                    risks = json.loads(json_match.group())
                    return self._process_risks(risks)
                except json.JSONDecodeError:
                    logger.error("Failed to parse risks JSON")
                    return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error analyzing risks: {str(e)}")
            return []
    
    async def identify_opportunities(self,
                                   structured_data: Dict,
                                   products: List[Dict],
                                   risks: List[Dict]) -> List[Dict]:
        """
        Identifica oportunidades de negócio
        """
        total_value = sum(p.get('valor_total', 0) for p in products)
        
        prompt = f"""
        Com base na análise do edital, identifique OPORTUNIDADES DE NEGÓCIO.
        
        RESUMO DO EDITAL:
        - Objeto: {structured_data.get('objeto', '')}
        - Valor Total: R$ {total_value:,.2f}
        - Quantidade de Itens: {len(products)}
        - Órgão: {structured_data.get('orgao', '')}
        - Riscos Identificados: {len(risks)}
        
        PRODUTOS PRINCIPAIS (top 5 por valor):
        {self._format_top_products(products, 5)}
        
        Identifique oportunidades considerando:
        1. VOLUME: Grandes quantidades que permitem economia de escala
        2. VALOR: Itens de alto valor com boa margem potencial
        3. RECORRÊNCIA: Possibilidade de fornecimento contínuo
        4. ESTRATÉGICO: Entrada em novo cliente/segmento
        5. COMPETITIVO: Baixa concorrência ou vantagem competitiva
        
        Para cada oportunidade, forneça:
        - tipo: Categoria da oportunidade
        - titulo: Título descritivo
        - descricao: Descrição detalhada
        - valor_estimado: Valor potencial em R$
        - probabilidade_sucesso: Alta, Média ou Baixa
        - investimento_necessario: Estimativa de investimento
        - prazo_retorno: Prazo estimado de retorno
        
        Retorne uma lista JSON de oportunidades.
        """
        
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
                options={"temperature": 0.4}
            )
            
            result_text = response['response']
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            
            if json_match:
                try:
                    opportunities = json.loads(json_match.group())
                    return self._process_opportunities(opportunities)
                except json.JSONDecodeError:
                    logger.error("Failed to parse opportunities JSON")
                    return []
            
            return []
            
        except Exception as e:
            logger.error(f"Error identifying opportunities: {str(e)}")
            return []
    
    def _is_product_table(self, table: Dict) -> bool:
        """Check if table contains products"""
        headers = table.get('headers', [])
        if not headers:
            return False
        
        headers_text = ' '.join([str(h).lower() for h in headers])
        product_indicators = ['item', 'produto', 'descrição', 'quantidade', 'valor', 'preço']
        
        matches = sum(1 for indicator in product_indicators if indicator in headers_text)
        return matches >= 2
    
    def _combine_analyses(self, analyses: List[Dict]) -> Dict[str, Any]:
        """Combine multiple chunk analyses"""
        combined = {}
        
        for analysis in analyses:
            for key, value in analysis.items():
                if value and (not combined.get(key) or value != "Não informado"):
                    combined[key] = value
        
        return combined
    
    async def _refine_analysis(self, 
                              analysis: Dict, 
                              full_text: str,
                              tables: List[Dict]) -> Dict[str, Any]:
        """Refine and validate analysis"""
        
        # Validate and clean extracted data
        refined = analysis.copy()
        
        # Ensure required fields
        required_fields = ['numero_pregao', 'objeto', 'orgao']
        for field in required_fields:
            if not refined.get(field):
                # Try to extract from text
                refined[field] = self._extract_from_text(full_text, field)
        
        # Parse dates
        if refined.get('data_abertura'):
            refined['data_abertura'] = self._parse_date(refined['data_abertura'])
        
        # Parse monetary values
        if refined.get('valor_estimado'):
            refined['valor_estimado'] = self._parse_money(refined['valor_estimado'])
        
        return refined
    
    def _extract_from_text(self, text: str, field: str) -> Optional[str]:
        """Extract field from text using regex"""
        patterns = {
            'numero_pregao': r'Pregão\s+(?:Eletrônico\s+)?n[º°]?\s*(\d+/\d+)',
            'uasg': r'UASG\s*:?\s*(\d+)',
            'orgao': r'(?:Órgão|ÓRGÃO)\s*:?\s*([^\n]+)'
        }
        
        pattern = patterns.get(field)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        if not date_str:
            return None
        
        # Try common formats
        formats = [
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue
        
        return date_str
    
    def _parse_money(self, value: Any) -> float:
        """Parse monetary value"""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove currency symbols and separators
            value = re.sub(r'[R$\s.]', '', value)
            value = value.replace(',', '.')
            
            try:
                return float(value)
            except ValueError:
                return 0.0
        
        return 0.0
    
    def _format_top_products(self, products: List[Dict], limit: int = 5) -> str:
        """Format top products for prompt"""
        sorted_products = sorted(
            products, 
            key=lambda x: x.get('valor_total', 0), 
            reverse=True
        )[:limit]
        
        formatted = []
        for i, product in enumerate(sorted_products, 1):
            formatted.append(
                f"{i}. {product.get('descricao', 'Sem descrição')[:100]} - "
                f"Qtd: {product.get('quantidade', 0)} - "
                f"Valor: R$ {product.get('valor_total', 0):,.2f}"
            )
        
        return '\n'.join(formatted)
    
    def _process_risks(self, risks: List[Dict]) -> List[Dict]:
        """Process and score risks"""
        processed = []
        
        probability_scores = {'alta': 0.8, 'média': 0.5, 'baixa': 0.2}
        impact_scores = {'alto': 0.9, 'médio': 0.5, 'baixo': 0.2}
        
        for risk in risks:
            prob = probability_scores.get(
                risk.get('probabilidade', '').lower(), 
                0.5
            )
            imp = impact_scores.get(
                risk.get('impacto', '').lower(), 
                0.5
            )
            
            risk['probability'] = prob
            risk['impact'] = imp
            risk['risk_score'] = prob * imp
            
            # Determine severity
            if risk['risk_score'] >= 0.7:
                risk['severity'] = 'critical'
            elif risk['risk_score'] >= 0.4:
                risk['severity'] = 'high'
            elif risk['risk_score'] >= 0.2:
                risk['severity'] = 'medium'
            else:
                risk['severity'] = 'low'
            
            processed.append(risk)
        
        return sorted(processed, key=lambda x: x['risk_score'], reverse=True)
    
    def _process_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """Process and score opportunities"""
        processed = []
        
        success_scores = {'alta': 0.8, 'média': 0.5, 'baixa': 0.2}
        
        for opp in opportunities:
            success_prob = success_scores.get(
                opp.get('probabilidade_sucesso', '').lower(),
                0.5
            )
            
            # Calculate opportunity score
            value = self._parse_money(opp.get('valor_estimado', 0))
            investment = self._parse_money(opp.get('investimento_necessario', 0))
            
            if investment > 0:
                roi = (value - investment) / investment
            else:
                roi = 0
            
            opp['success_probability'] = success_prob
            opp['estimated_value'] = value
            opp['roi_estimate'] = roi
            opp['opportunity_score'] = min(100, success_prob * 50 + min(roi * 10, 50))
            
            # Determine priority
            if opp['opportunity_score'] >= 70:
                opp['priority'] = 'critical'
            elif opp['opportunity_score'] >= 50:
                opp['priority'] = 'high'
            elif opp['opportunity_score'] >= 30:
                opp['priority'] = 'medium'
            else:
                opp['priority'] = 'low'
            
            processed.append(opp)
        
        return sorted(processed, key=lambda x: x['opportunity_score'], reverse=True)

class AIEngine:
    """Motor principal de IA combinando Docling e Llama"""
    
    def __init__(self):
        self.docling = DoclingProcessor()
        self.llama = LlamaAnalyzer()
        
    async def initialize_models(self):
        """Initialize AI models"""
        logger.info("Initializing AI models...")
        
        # Ensure Llama model is available
        self.llama._ensure_model()
        
        logger.info("AI models initialized successfully")
    
    async def process_edital(self, 
                            file_path: str,
                            metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process complete edital with AI pipeline
        """
        logger.info(f"Starting AI processing for {file_path}")
        
        # Step 1: Process with Docling
        docling_result = await self.docling.process_document(file_path)
        
        # Step 2: Analyze with Llama
        llama_analysis = await self.llama.analyze_edital(
            text=docling_result.get('text', ''),
            tables=docling_result.get('tables', []),
            metadata=metadata
        )
        
        # Step 3: Extract products
        products = await self.llama.extract_products(
            tables=docling_result.get('tables', [])
        )
        
        # Step 4: Analyze risks
        risks = await self.llama.analyze_risks(
            text=docling_result.get('text', ''),
            structured_data=llama_analysis,
            products=products
        )
        
        # Step 5: Identify opportunities
        opportunities = await self.llama.identify_opportunities(
            structured_data=llama_analysis,
            products=products,
            risks=risks
        )
        
        # Compile final result
        result = {
            'structured_data': llama_analysis,
            'products': products,
            'risks': risks,
            'opportunities': opportunities,
            'document_structure': {
                'sections': docling_result.get('sections', {}),
                'tables_count': len(docling_result.get('tables', [])),
                'pages': docling_result.get('metadata', {}).get('pages', 0)
            },
            'quality_metrics': self._calculate_quality_metrics(
                llama_analysis, products, risks, opportunities
            )
        }
        
        logger.info("AI processing completed successfully")
        return result
    
    def _calculate_quality_metrics(self,
                                  analysis: Dict,
                                  products: List,
                                  risks: List,
                                  opportunities: List) -> Dict[str, float]:
        """Calculate quality metrics for extraction"""
        metrics = {
            'completeness': 0.0,
            'confidence': 0.0,
            'data_richness': 0.0
        }
        
        # Completeness score
        required_fields = ['numero_pregao', 'objeto', 'orgao', 'valor_estimado']
        found_fields = sum(1 for field in required_fields if analysis.get(field))
        metrics['completeness'] = found_fields / len(required_fields)
        
        # Confidence score (based on data extracted)
        if products:
            metrics['confidence'] += 0.3
        if risks:
            metrics['confidence'] += 0.3
        if opportunities:
            metrics['confidence'] += 0.4
        
        # Data richness
        metrics['data_richness'] = min(1.0, (
            len(products) * 0.02 +
            len(risks) * 0.1 +
            len(opportunities) * 0.1
        ))
        
        return metrics