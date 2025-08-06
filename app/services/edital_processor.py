# app/services/edital_processor.py
"""
Fluxo completo de processamento de editais com todas as etapas detalhadas
"""
import asyncio
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
import logging

from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ProcessingStage(Enum):
    """Estágios do processamento"""
    VALIDATION = "validation"
    TEXT_EXTRACTION = "text_extraction"
    OCR_PROCESSING = "ocr_processing"
    TABLE_DETECTION = "table_detection"
    TABLE_EXTRACTION = "table_extraction"
    AI_PREPROCESSING = "ai_preprocessing"
    AI_ANALYSIS = "ai_analysis"
    STRUCTURE_EXTRACTION = "structure_extraction"
    RISK_ANALYSIS = "risk_analysis"
    OPPORTUNITY_IDENTIFICATION = "opportunity_identification"
    QUALITY_VALIDATION = "quality_validation"
    RESULT_COMPILATION = "result_compilation"
    STORAGE = "storage"
    NOTIFICATION = "notification"

@dataclass
class EditalInfo:
    """Informações estruturadas do edital"""
    numero_pregao: str
    uasg: str
    orgao: str
    objeto: str
    valor_estimado: float
    data_abertura: datetime
    modalidade: str
    tipo_licitacao: str
    criterio_julgamento: str

@dataclass
class ProcessingContext:
    """Contexto de processamento com todos os dados intermediários"""
    task_id: str
    file_path: Path
    raw_text: str = ""
    ocr_text: str = ""
    tables: List[Dict] = None
    product_tables: List[Dict] = None
    ai_analysis: Dict = None
    structured_data: EditalInfo = None
    risks: List[Dict] = None
    opportunities: List[Dict] = None
    quality_score: float = 0.0
    processing_times: Dict[str, float] = None
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        self.tables = self.tables or []
        self.product_tables = self.product_tables or []
        self.ai_analysis = self.ai_analysis or {}
        self.risks = self.risks or []
        self.opportunities = self.opportunities or []
        self.processing_times = self.processing_times or {}
        self.errors = self.errors or []
        self.warnings = self.warnings or []

class EditalProcessingPipeline:
    """Pipeline principal de processamento de editais"""
    
    def __init__(self, 
                 pdf_processor,
                 ocr_engine, 
                 table_extractor,
                 ai_engine,
                 risk_analyzer,
                 storage_manager):
        self.pdf_processor = pdf_processor
        self.ocr_engine = ocr_engine
        self.table_extractor = table_extractor
        self.ai_engine = ai_engine
        self.risk_analyzer = risk_analyzer
        self.storage_manager = storage_manager
        
    async def process_edital(self, 
                            task_id: str, 
                            file_path: str,
                            metadata: Dict[str, Any],
                            progress_callback=None) -> Dict[str, Any]:
        """
        Processa um edital através de todo o pipeline
        """
        context = ProcessingContext(
            task_id=task_id,
            file_path=Path(file_path)
        )
        
        stages = [
            (ProcessingStage.VALIDATION, self._validate_document),
            (ProcessingStage.TEXT_EXTRACTION, self._extract_text),
            (ProcessingStage.OCR_PROCESSING, self._process_ocr),
            (ProcessingStage.TABLE_DETECTION, self._detect_tables),
            (ProcessingStage.TABLE_EXTRACTION, self._extract_tables),
            (ProcessingStage.AI_PREPROCESSING, self._preprocess_for_ai),
            (ProcessingStage.AI_ANALYSIS, self._analyze_with_ai),
            (ProcessingStage.STRUCTURE_EXTRACTION, self._extract_structure),
            (ProcessingStage.RISK_ANALYSIS, self._analyze_risks),
            (ProcessingStage.OPPORTUNITY_IDENTIFICATION, self._identify_opportunities),
            (ProcessingStage.QUALITY_VALIDATION, self._validate_quality),
            (ProcessingStage.RESULT_COMPILATION, self._compile_results),
            (ProcessingStage.STORAGE, self._store_results),
            (ProcessingStage.NOTIFICATION, self._send_notifications)
        ]
        
        total_stages = len(stages)
        
        for idx, (stage, processor) in enumerate(stages):
            start_time = datetime.now()
            
            try:
                logger.info(f"Starting stage: {stage.value}")
                
                # Update progress
                if progress_callback:
                    progress = int((idx / total_stages) * 100)
                    await progress_callback(progress, f"Executando: {stage.value}")
                
                # Execute stage
                await processor(context, metadata)
                
                # Record timing
                elapsed = (datetime.now() - start_time).total_seconds()
                context.processing_times[stage.value] = elapsed
                
                logger.info(f"Completed stage: {stage.value} in {elapsed:.2f}s")
                
            except Exception as e:
                logger.error(f"Error in stage {stage.value}: {str(e)}")
                context.errors.append(f"{stage.value}: {str(e)}")
                
                # Decide if error is critical
                if self._is_critical_stage(stage):
                    raise
                else:
                    context.warnings.append(f"Stage {stage.value} failed but continuing")
        
        # Final progress update
        if progress_callback:
            await progress_callback(100, "Processamento concluído")
        
        return self._build_final_result(context)
    
    async def _validate_document(self, context: ProcessingContext, metadata: Dict):
        """Valida o documento PDF"""
        file_path = context.file_path
        
        # Check file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > 100 * 1024 * 1024:  # 100MB limit
            raise ValueError(f"File too large: {file_size} bytes")
        
        # Validate PDF structure
        is_valid, pdf_info = self.pdf_processor.validate_pdf(str(file_path))
        if not is_valid:
            raise ValueError(f"Invalid PDF: {pdf_info.get('error')}")
        
        # Check for encryption
        if pdf_info.get('encrypted'):
            raise ValueError("PDF is encrypted")
        
        # Store PDF metadata
        context.ai_analysis['pdf_metadata'] = pdf_info
    
    async def _extract_text(self, context: ProcessingContext, metadata: Dict):
        """Extrai texto do PDF"""
        text, extraction_info = self.pdf_processor.extract_text_with_layout(
            str(context.file_path)
        )
        
        context.raw_text = text
        context.ai_analysis['extraction_info'] = extraction_info
        
        # Identify sections
        sections = self._identify_sections(text)
        context.ai_analysis['sections'] = sections
    
    async def _process_ocr(self, context: ProcessingContext, metadata: Dict):
        """Processa páginas com OCR se necessário"""
        # Check if OCR is needed
        if self._needs_ocr(context.raw_text):
            logger.info("OCR processing required")
            ocr_results = await self.ocr_engine.process_pdf(
                str(context.file_path),
                languages=['por', 'eng']
            )
            
            context.ocr_text = ocr_results['text']
            context.ai_analysis['ocr_confidence'] = ocr_results['confidence']
            
            # Merge OCR text with extracted text
            context.raw_text = self._merge_texts(context.raw_text, context.ocr_text)
    
    async def _detect_tables(self, context: ProcessingContext, metadata: Dict):
        """Detecta tabelas no documento"""
        # Use multiple detection methods
        detection_results = await self.table_extractor.detect_tables_multi_method(
            str(context.file_path)
        )
        
        context.ai_analysis['table_regions'] = detection_results['regions']
        context.ai_analysis['table_count'] = len(detection_results['regions'])
    
    async def _extract_tables(self, context: ProcessingContext, metadata: Dict):
        """Extrai dados das tabelas detectadas"""
        tables = []
        
        for region in context.ai_analysis.get('table_regions', []):
            table_data = await self.table_extractor.extract_table_data(
                str(context.file_path),
                region
            )
            
            # Classify table type
            table_type = self._classify_table(table_data)
            table_data['type'] = table_type
            
            # Clean and structure table data
            if table_type == 'products':
                table_data = self._structure_product_table(table_data)
                context.product_tables.append(table_data)
            
            tables.append(table_data)
        
        context.tables = tables
    
    async def _preprocess_for_ai(self, context: ProcessingContext, metadata: Dict):
        """Prepara dados para análise de IA"""
        # Create structured prompt
        prompt_data = {
            'text': context.raw_text,
            'tables': context.product_tables,
            'metadata': metadata,
            'sections': context.ai_analysis.get('sections', {})
        }
        
        # Chunk text if too large
        if len(context.raw_text) > 30000:
            chunks = self._chunk_text(context.raw_text, max_length=10000)
            prompt_data['chunks'] = chunks
        
        context.ai_analysis['prompt_data'] = prompt_data
    
    async def _analyze_with_ai(self, context: ProcessingContext, metadata: Dict):
        """Análise principal com IA"""
        prompt_data = context.ai_analysis['prompt_data']
        
        # Prepare specific prompts for different aspects
        prompts = {
            'extraction': self._build_extraction_prompt(prompt_data),
            'understanding': self._build_understanding_prompt(prompt_data),
            'validation': self._build_validation_prompt(prompt_data)
        }
        
        # Run AI analysis
        ai_results = {}
        for task, prompt in prompts.items():
            result = await self.ai_engine.analyze(
                prompt=prompt,
                temperature=0.1,  # Low temperature for consistency
                max_tokens=4096
            )
            ai_results[task] = result
        
        # Parse and structure AI results
        context.ai_analysis['ai_results'] = ai_results
        
        # Extract key information
        self._extract_key_information(context, ai_results)
    
    async def _extract_structure(self, context: ProcessingContext, metadata: Dict):
        """Extrai estrutura do edital"""
        ai_extraction = context.ai_analysis.get('ai_results', {}).get('extraction', {})
        
        # Parse structured information
        context.structured_data = EditalInfo(
            numero_pregao=self._extract_field(ai_extraction, 'numero_pregao', metadata.get('numero_pregao')),
            uasg=self._extract_field(ai_extraction, 'uasg', metadata.get('uasg')),
            orgao=self._extract_field(ai_extraction, 'orgao'),
            objeto=self._extract_field(ai_extraction, 'objeto'),
            valor_estimado=self._extract_monetary_value(ai_extraction, 'valor_estimado'),
            data_abertura=self._extract_datetime(ai_extraction, 'data_abertura'),
            modalidade=self._extract_field(ai_extraction, 'modalidade', 'Pregão Eletrônico'),
            tipo_licitacao=self._extract_field(ai_extraction, 'tipo_licitacao', 'Menor Preço'),
            criterio_julgamento=self._extract_field(ai_extraction, 'criterio_julgamento')
        )
    
    async def _analyze_risks(self, context: ProcessingContext, metadata: Dict):
        """Analisa riscos do edital"""
        risks = []
        
        # Technical risks
        tech_risks = self.risk_analyzer.analyze_technical_risks(
            context.raw_text,
            context.product_tables
        )
        risks.extend(tech_risks)
        
        # Legal risks
        legal_risks = self.risk_analyzer.analyze_legal_risks(
            context.raw_text,
            context.structured_data
        )
        risks.extend(legal_risks)
        
        # Commercial risks
        commercial_risks = self.risk_analyzer.analyze_commercial_risks(
            context.structured_data,
            context.product_tables
        )
        risks.extend(commercial_risks)
        
        # Prioritize risks
        context.risks = self._prioritize_risks(risks)
    
    async def _identify_opportunities(self, context: ProcessingContext, metadata: Dict):
        """Identifica oportunidades de negócio"""
        opportunities = []
        
        # Product opportunities
        for table in context.product_tables:
            product_opps = self._analyze_product_opportunities(table)
            opportunities.extend(product_opps)
        
        # Value opportunities
        if context.structured_data.valor_estimado > 0:
            value_opps = self._analyze_value_opportunities(
                context.structured_data.valor_estimado,
                context.product_tables
            )
            opportunities.extend(value_opps)
        
        # Strategic opportunities
        strategic_opps = self._analyze_strategic_opportunities(
            context.structured_data,
            context.ai_analysis
        )
        opportunities.extend(strategic_opps)
        
        context.opportunities = opportunities
    
    async def _validate_quality(self, context: ProcessingContext, metadata: Dict):
        """Valida qualidade da extração"""
        scores = {
            'text_extraction': self._score_text_extraction(context),
            'table_extraction': self._score_table_extraction(context),
            'ai_extraction': self._score_ai_extraction(context),
            'completeness': self._score_completeness(context),
            'consistency': self._score_consistency(context)
        }
        
        # Calculate weighted average
        weights = {
            'text_extraction': 0.2,
            'table_extraction': 0.25,
            'ai_extraction': 0.25,
            'completeness': 0.15,
            'consistency': 0.15
        }
        
        total_score = sum(scores[k] * weights[k] for k in scores)
        context.quality_score = round(total_score, 2)
        
        # Add quality details
        context.ai_analysis['quality_details'] = scores
    
    async def _compile_results(self, context: ProcessingContext, metadata: Dict):
        """Compila resultados finais"""
        # Aggregate all processing results
        context.ai_analysis['final_summary'] = {
            'total_pages': context.ai_analysis.get('pdf_metadata', {}).get('pages', 0),
            'tables_found': len(context.tables),
            'product_tables': len(context.product_tables),
            'total_items': sum(len(t.get('rows', [])) for t in context.product_tables),
            'risks_identified': len(context.risks),
            'opportunities_found': len(context.opportunities),
            'quality_score': context.quality_score,
            'processing_time': sum(context.processing_times.values())
        }
    
    async def _store_results(self, context: ProcessingContext, metadata: Dict):
        """Armazena resultados processados"""
        result_data = self._build_final_result(context)
        
        # Store in database
        await self.storage_manager.store_result(
            task_id=context.task_id,
            result=result_data
        )
        
        # Store files
        await self.storage_manager.organize_files(
            task_id=context.task_id,
            source_file=context.file_path,
            metadata=metadata,
            result=result_data
        )
    
    async def _send_notifications(self, context: ProcessingContext, metadata: Dict):
        """Envia notificações de conclusão"""
        if metadata.get('callback_url'):
            await self._send_callback(
                url=metadata['callback_url'],
                data={
                    'task_id': context.task_id,
                    'status': 'completed',
                    'quality_score': context.quality_score,
                    'summary': context.ai_analysis.get('final_summary', {})
                }
            )
    
    # Helper methods
    def _identify_sections(self, text: str) -> Dict[str, str]:
        """Identifica seções do edital"""
        sections = {}
        patterns = {
            'objeto': r'(?:OBJETO|1\s*[-–]\s*DO\s+OBJETO)(.*?)(?:2\s*[-–]|\n\n)',
            'valor': r'(?:VALOR|ESTIMADO|ORÇAMENTO)(.*?)(?:\n\n|$)',
            'prazo': r'(?:PRAZO|ENTREGA|EXECUÇÃO)(.*?)(?:\n\n|$)',
            'pagamento': r'(?:PAGAMENTO|CONDIÇÕES)(.*?)(?:\n\n|$)',
            'habilitacao': r'(?:HABILITAÇÃO|DOCUMENTOS)(.*?)(?:\n\n|$)'
        }
        
        for section, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                sections[section] = match.group(1).strip()[:1000]
        
        return sections
    
    def _needs_ocr(self, text: str) -> bool:
        """Verifica se precisa OCR"""
        # Check if text is too short or has too many special characters
        if len(text) < 100:
            return True
        
        # Check for readable content ratio
        readable_chars = sum(1 for c in text if c.isalnum() or c.isspace())
        ratio = readable_chars / len(text)
        
        return ratio < 0.7
    
    def _merge_texts(self, text1: str, text2: str) -> str:
        """Merge extracted and OCR text"""
        if not text1:
            return text2
        if not text2:
            return text1
        
        # Simple merge strategy - could be enhanced
        return f"{text1}\n\n--- OCR Content ---\n\n{text2}"
    
    def _classify_table(self, table_data: Dict) -> str:
        """Classifica o tipo de tabela"""
        headers = table_data.get('headers', [])
        headers_lower = [h.lower() for h in headers if h]
        
        # Product table indicators
        product_indicators = ['item', 'descrição', 'quantidade', 'valor', 'preço', 'produto']
        if any(ind in ' '.join(headers_lower) for ind in product_indicators):
            return 'products'
        
        # Other table types
        if any('documento' in h for h in headers_lower):
            return 'documents'
        if any('prazo' in h for h in headers_lower):
            return 'schedule'
        
        return 'other'
    
    def _structure_product_table(self, table_data: Dict) -> Dict:
        """Estrutura tabela de produtos"""
        structured = {
            'type': 'products',
            'headers': table_data.get('headers', []),
            'rows': []
        }
        
        for row in table_data.get('data', []):
            structured_row = self._parse_product_row(row, structured['headers'])
            if structured_row:
                structured['rows'].append(structured_row)
        
        return structured
    
    def _parse_product_row(self, row: List, headers: List) -> Optional[Dict]:
        """Parse uma linha de produto"""
        if not row or len(row) < 2:
            return None
        
        parsed = {}
        header_map = {
            'item': ['item', 'nº', 'numero'],
            'description': ['descrição', 'descricao', 'especificação'],
            'quantity': ['quantidade', 'qtd', 'quant'],
            'unit': ['unidade', 'un', 'medida'],
            'unit_price': ['valor unitário', 'preço unitário', 'vlr unit'],
            'total_price': ['valor total', 'total', 'vlr total']
        }
        
        for i, value in enumerate(row):
            if i < len(headers):
                header_lower = headers[i].lower()
                for field, keywords in header_map.items():
                    if any(kw in header_lower for kw in keywords):
                        parsed[field] = self._parse_value(value, field)
                        break
        
        return parsed if parsed else None
    
    def _parse_value(self, value: str, field_type: str) -> Any:
        """Parse valor baseado no tipo"""
        if not value:
            return None
        
        if field_type in ['quantity', 'unit_price', 'total_price']:
            # Parse numeric values
            value = re.sub(r'[^\d,.-]', '', str(value))
            value = value.replace(',', '.')
            try:
                return float(value)
            except:
                return 0.0
        
        return str(value).strip()
    
    def _chunk_text(self, text: str, max_length: int = 10000) -> List[str]:
        """Divide texto em chunks"""
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1
            if current_length + word_length > max_length:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _build_extraction_prompt(self, data: Dict) -> str:
        """Constrói prompt para extração"""
        return f"""
        Analise o seguinte edital e extraia as informações estruturadas:
        
        Texto: {data['text'][:5000]}
        
        Extraia:
        1. Número do pregão
        2. UASG
        3. Órgão
        4. Objeto detalhado
        5. Valor estimado
        6. Data de abertura
        7. Modalidade
        8. Tipo de licitação
        9. Critério de julgamento
        
        Retorne em formato JSON estruturado.
        """
    
    def _build_understanding_prompt(self, data: Dict) -> str:
        """Constrói prompt para compreensão"""
        return f"""
        Analise o contexto deste edital e identifique:
        
        1. Principais requisitos técnicos
        2. Condições especiais
        3. Restrições importantes
        4. Pontos de atenção
        
        Texto: {data['text'][:5000]}
        """
    
    def _build_validation_prompt(self, data: Dict) -> str:
        """Constrói prompt para validação"""
        return f"""
        Valide as seguintes informações extraídas do edital:
        
        Tabelas encontradas: {len(data.get('tables', []))}
        Seções identificadas: {list(data.get('sections', {}).keys())}
        
        Confirme se a extração está completa e coerente.
        """
    
    def _extract_field(self, data: Dict, field: str, default: Any = None) -> Any:
        """Extrai campo dos resultados da IA"""
        return data.get(field, default)
    
    def _extract_monetary_value(self, data: Dict, field: str) -> float:
        """Extrai valor monetário"""
        value = data.get(field, '0')
        if isinstance(value, (int, float)):
            return float(value)
        
        # Parse string value
        value = re.sub(r'[^\d,.-]', '', str(value))
        value = value.replace('.', '').replace(',', '.')
        
        try:
            return float(value)
        except:
            return 0.0
    
    def _extract_datetime(self, data: Dict, field: str) -> Optional[datetime]:
        """Extrai datetime"""
        date_str = data.get(field)
        if not date_str:
            return None
        
        # Try common date formats
        formats = [
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        return None
    
    def _prioritize_risks(self, risks: List[Dict]) -> List[Dict]:
        """Prioriza riscos por severidade"""
        for risk in risks:
            # Calculate risk score
            probability = risk.get('probability', 0.5)
            impact = risk.get('impact', 0.5)
            risk['score'] = probability * impact
        
        # Sort by score
        return sorted(risks, key=lambda x: x['score'], reverse=True)
    
    def _analyze_product_opportunities(self, table: Dict) -> List[Dict]:
        """Analisa oportunidades em produtos"""
        opportunities = []
        
        for row in table.get('rows', []):
            if row.get('quantity', 0) > 100:
                opportunities.append({
                    'type': 'volume',
                    'description': f"Alto volume: {row.get('description', 'Item')}",
                    'value': row.get('total_price', 0),
                    'confidence': 0.8
                })
        
        return opportunities
    
    def _analyze_value_opportunities(self, total_value: float, tables: List) -> List[Dict]:
        """Analisa oportunidades de valor"""
        opportunities = []
        
        if total_value > 500000:
            opportunities.append({
                'type': 'high_value',
                'description': f"Contrato de alto valor: R$ {total_value:,.2f}",
                'value': total_value,
                'confidence': 0.9
            })
        
        return opportunities
    
    def _analyze_strategic_opportunities(self, data: EditalInfo, analysis: Dict) -> List[Dict]:
        """Analisa oportunidades estratégicas"""
        opportunities = []
        
        # Check for recurring contracts
        if 'registro de preços' in data.objeto.lower():
            opportunities.append({
                'type': 'recurring',
                'description': "Registro de preços - possibilidade de fornecimento contínuo",
                'confidence': 0.85
            })
        
        return opportunities
    
    def _score_text_extraction(self, context: ProcessingContext) -> float:
        """Pontuação da extração de texto"""
        if not context.raw_text:
            return 0.0
        
        text_length = len(context.raw_text)
        if text_length < 1000:
            return 0.3
        elif text_length < 5000:
            return 0.6
        else:
            return 1.0
    
    def _score_table_extraction(self, context: ProcessingContext) -> float:
        """Pontuação da extração de tabelas"""
        if not context.tables:
            return 0.3
        
        # Check table quality
        valid_tables = sum(1 for t in context.tables if len(t.get('rows', [])) > 0)
        
        if valid_tables == 0:
            return 0.3
        elif valid_tables < 3:
            return 0.7
        else:
            return 1.0
    
    def _score_ai_extraction(self, context: ProcessingContext) -> float:
        """Pontuação da extração por IA"""
        if not context.structured_data:
            return 0.0
        
        required_fields = ['numero_pregao', 'objeto', 'valor_estimado']
        found_fields = sum(1 for f in required_fields if getattr(context.structured_data, f, None))
        
        return found_fields / len(required_fields)
    
    def _score_completeness(self, context: ProcessingContext) -> float:
        """Pontuação de completude"""
        components = [
            bool(context.raw_text),
            bool(context.tables),
            bool(context.structured_data),
            bool(context.risks),
            bool(context.opportunities)
        ]
        
        return sum(components) / len(components)
    
    def _score_consistency(self, context: ProcessingContext) -> float:
        """Pontuação de consistência"""
        # Check for errors and warnings
        error_penalty = len(context.errors) * 0.1
        warning_penalty = len(context.warnings) * 0.05
        
        score = 1.0 - error_penalty - warning_penalty
        return max(0.0, score)
    
    def _is_critical_stage(self, stage: ProcessingStage) -> bool:
        """Verifica se o estágio é crítico"""
        critical_stages = [
            ProcessingStage.VALIDATION,
            ProcessingStage.TEXT_EXTRACTION,
            ProcessingStage.AI_ANALYSIS
        ]
        return stage in critical_stages
    
    def _build_final_result(self, context: ProcessingContext) -> Dict[str, Any]:
        """Constrói resultado final"""
        return {
            'task_id': context.task_id,
            'file_path': str(context.file_path),
            'structured_data': context.structured_data.__dict__ if context.structured_data else {},
            'tables': context.tables,
            'product_tables': context.product_tables,
            'risks': context.risks,
            'opportunities': context.opportunities,
            'quality_score': context.quality_score,
            'processing_times': context.processing_times,
            'errors': context.errors,
            'warnings': context.warnings,
            'analysis': context.ai_analysis,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _send_callback(self, url: str, data: Dict):
        """Envia callback"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        logger.error(f"Callback failed: {response.status}")
            except Exception as e:
                logger.error(f"Callback error: {str(e)}")