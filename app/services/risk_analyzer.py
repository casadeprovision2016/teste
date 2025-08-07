# app/services/risk_analyzer.py
"""
Risk analysis and opportunity identification for government procurement documents
"""
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "baixa"
    MEDIUM = "média" 
    HIGH = "alta"
    CRITICAL = "crítica"

class RiskType(Enum):
    TECHNICAL = "técnico"
    LEGAL = "legal"
    COMMERCIAL = "comercial"
    OPERATIONAL = "operacional"
    FINANCIAL = "financeiro"
    COMPLIANCE = "conformidade"

@dataclass
class RiskPattern:
    keywords: List[str]
    risk_type: RiskType
    base_probability: float
    base_impact: float
    description_template: str
    mitigation_template: str

class RiskAnalyzer:
    """Advanced risk analyzer for procurement documents"""
    
    def __init__(self):
        self.risk_patterns = self._load_risk_patterns()
        self.opportunity_patterns = self._load_opportunity_patterns()
        
    def _load_risk_patterns(self) -> List[RiskPattern]:
        """Load predefined risk patterns for Brazilian procurement"""
        return [
            # Technical Risks
            RiskPattern(
                keywords=["especificação técnica", "norma técnica", "certificação", "homologação", "padrão técnico", "requisitos técnicos"],
                risk_type=RiskType.TECHNICAL,
                base_probability=0.6,
                base_impact=0.7,
                description_template="Risco técnico relacionado a {keyword}. Pode haver dificuldades na conformidade técnica ou certificações necessárias.",
                mitigation_template="Verificar antecipadamente todas as certificações e normas técnicas exigidas. Consultar fabricantes sobre conformidade."
            ),
            
            RiskPattern(
                keywords=["instalação", "montagem", "configuração", "implementação", "integração"],
                risk_type=RiskType.TECHNICAL,
                base_probability=0.5,
                base_impact=0.6,
                description_template="Complexidade na {keyword} pode gerar atrasos ou custos adicionais.",
                mitigation_template="Planejar detalhadamente a fase de {keyword}. Alocar recursos técnicos especializados."
            ),
            
            # Legal/Compliance Risks
            RiskPattern(
                keywords=["licitação", "habilitação", "documentação", "certidão", "regularidade fiscal", "trabalhista"],
                risk_type=RiskType.LEGAL,
                base_probability=0.4,
                base_impact=0.8,
                description_template="Risco de inabilitação por questões de {keyword}.",
                mitigation_template="Manter documentação sempre atualizada. Verificar prazos de validade regularmente."
            ),
            
            RiskPattern(
                keywords=["prazo de entrega", "cronograma", "data limite", "urgência", "emergencial"],
                risk_type=RiskType.OPERATIONAL,
                base_probability=0.7,
                base_impact=0.6,
                description_template="Prazos apertados para {keyword} podem comprometer a qualidade ou viabilidade.",
                mitigation_template="Avaliar capacidade operacional. Considerar parcerias ou terceirização se necessário."
            ),
            
            # Commercial/Financial Risks
            RiskPattern(
                keywords=["menor preço", "maior desconto", "proposta mais vantajosa", "lance mínimo"],
                risk_type=RiskType.COMMERCIAL,
                base_probability=0.8,
                base_impact=0.5,
                description_template="Alta competitividade por {keyword} pode pressionar margens.",
                mitigation_template="Otimizar custos operacionais. Considerar diferenciação técnica ou qualidade."
            ),
            
            RiskPattern(
                keywords=["garantia", "assistência técnica", "manutenção", "suporte técnico", "pós-venda"],
                risk_type=RiskType.OPERATIONAL,
                base_probability=0.5,
                base_impact=0.7,
                description_template="Obrigações de {keyword} podem gerar custos não previstos.",
                mitigation_template="Calcular custos de {keyword} no preço final. Estabelecer parcerias se necessário."
            ),
            
            # Volume and Scale Risks
            RiskPattern(
                keywords=["grande quantidade", "volume elevado", "escala", "lotes múltiplos"],
                risk_type=RiskType.OPERATIONAL,
                base_probability=0.6,
                base_impact=0.6,
                description_template="Risco operacional devido ao {keyword} exigido.",
                mitigation_template="Avaliar capacidade de fornecimento. Considerar parcerias para atender demanda."
            ),
            
            # Payment and Cash Flow Risks
            RiskPattern(
                keywords=["pagamento em", "prazo de pagamento", "30 dias", "45 dias", "60 dias"],
                risk_type=RiskType.FINANCIAL,
                base_probability=0.4,
                base_impact=0.5,
                description_template="Risco de fluxo de caixa devido ao prazo de {keyword}.",
                mitigation_template="Planejar fluxo de caixa considerando prazos de pagamento. Avaliar necessidade de capital de giro."
            ),
            
            # Geographic/Logistics Risks
            RiskPattern(
                keywords=["entrega em", "local de entrega", "região", "estado", "município", "logística"],
                risk_type=RiskType.OPERATIONAL,
                base_probability=0.3,
                base_impact=0.4,
                description_template="Desafios logísticos para {keyword} podem impactar custos e prazos.",
                mitigation_template="Verificar custos de transporte e logística para a região. Considerar parcerias locais."
            )
        ]
    
    def _load_opportunity_patterns(self) -> List[Dict[str, Any]]:
        """Load opportunity identification patterns"""
        return [
            {
                "keywords": ["ata de registro de preços", "arp", "contrato de fornecimento"],
                "opportunity_type": "recorrente",
                "score_multiplier": 1.5,
                "description": "Oportunidade de fornecimento recorrente através de ARP"
            },
            
            {
                "keywords": ["grande quantidade", "volume elevado", "lote único"],
                "opportunity_type": "volume",
                "score_multiplier": 1.3,
                "description": "Oportunidade de alto volume de vendas"
            },
            
            {
                "keywords": ["valor estimado acima", "alto valor", "grande contrato"],
                "opportunity_type": "valor",
                "score_multiplier": 1.4,
                "description": "Oportunidade de alto valor comercial"
            },
            
            {
                "keywords": ["exclusivo", "marca específica", "modelo específico", "fabricante único"],
                "opportunity_type": "estratégica",
                "score_multiplier": 1.2,
                "description": "Oportunidade estratégica com baixa concorrência"
            },
            
            {
                "keywords": ["primeira vez", "piloto", "projeto inovador", "tecnologia nova"],
                "opportunity_type": "estratégica",
                "score_multiplier": 1.6,
                "description": "Oportunidade estratégica de posicionamento em nova área"
            }
        ]
    
    def analyze(self, document_text: str, structured_data: Dict[str, Any], tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Comprehensive risk analysis of procurement document
        """
        logger.info("Starting comprehensive risk analysis")
        
        # Text-based risk analysis
        text_risks = self._analyze_text_risks(document_text)
        
        # Structured data risk analysis
        structured_risks = self._analyze_structured_risks(structured_data)
        
        # Table-based risk analysis
        table_risks = self._analyze_table_risks(tables)
        
        # Timeline and deadline risks
        deadline_risks = self._analyze_deadline_risks(document_text, structured_data)
        
        # Competition and market risks
        competition_risks = self._analyze_competition_risks(document_text, structured_data)
        
        # Combine all risks
        all_risks = text_risks + structured_risks + table_risks + deadline_risks + competition_risks
        
        # Remove duplicates and prioritize
        unique_risks = self._deduplicate_risks(all_risks)
        prioritized_risks = self._prioritize_risks(unique_risks)
        
        # Calculate overall risk assessment
        risk_summary = self._calculate_risk_summary(prioritized_risks)
        
        result = {
            "risks": prioritized_risks,
            "risk_summary": risk_summary,
            "analysis_metadata": {
                "total_risks_identified": len(prioritized_risks),
                "critical_risks": len([r for r in prioritized_risks if r.get("severity") == "crítica"]),
                "high_risks": len([r for r in prioritized_risks if r.get("severity") == "alta"]),
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
        }
        
        logger.info(f"Risk analysis completed: {len(prioritized_risks)} risks identified")
        return result
    
    def identify_opportunities(self, structured_data: Dict[str, Any], risk_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identify business opportunities from the procurement document
        """
        logger.info("Starting opportunity identification")
        
        opportunities = []
        
        # Extract key values
        estimated_value = structured_data.get("valor_estimado", 0)
        procurement_type = structured_data.get("modalidade", "")
        description = structured_data.get("objeto", "")
        
        # Value-based opportunities
        if estimated_value > 1000000:  # > R$ 1M
            opportunities.append({
                "opportunity_type": "valor",
                "title": "Contrato de Alto Valor",
                "description": f"Oportunidade de contrato com valor estimado de R$ {estimated_value:,.2f}",
                "estimated_value": estimated_value,
                "profit_potential": estimated_value * 0.15,  # 15% margin estimate
                "success_probability": 0.3,  # Lower due to high competition
                "opportunity_score": min(85, 50 + (estimated_value / 100000)),
                "priority": "alta",
                "competitive_advantage": "Necessário preço competitivo e capacidade operacional comprovada"
            })
        
        # Volume-based opportunities
        volume_indicators = ["grande quantidade", "volume", "lotes", "múltiplas unidades"]
        if any(indicator in description.lower() for indicator in volume_indicators):
            opportunities.append({
                "opportunity_type": "volume",
                "title": "Oportunidade de Alto Volume",
                "description": "Contrato com potencial de grandes volumes de fornecimento",
                "estimated_value": estimated_value,
                "profit_potential": estimated_value * 0.12,
                "success_probability": 0.4,
                "opportunity_score": 70,
                "priority": "média",
                "competitive_advantage": "Capacidade de produção/fornecimento em escala"
            })
        
        # Recurrent opportunities (ARP)
        if "ata de registro" in description.lower() or "arp" in procurement_type.lower():
            opportunities.append({
                "opportunity_type": "recorrente",
                "title": "Fornecimento Recorrente via ARP",
                "description": "Oportunidade de fornecimento recorrente através de Ata de Registro de Preços",
                "estimated_value": estimated_value * 2,  # Potential for multiple orders
                "profit_potential": estimated_value * 0.20,
                "success_probability": 0.5,
                "opportunity_score": 75,
                "priority": "alta",
                "competitive_advantage": "Relacionamento de longo prazo e previsibilidade de demanda"
            })
        
        # Strategic opportunities
        strategic_keywords = ["inovador", "tecnologia", "piloto", "primeira vez", "exclusivo"]
        if any(keyword in description.lower() for keyword in strategic_keywords):
            opportunities.append({
                "opportunity_type": "estratégica",
                "title": "Posicionamento Estratégico",
                "description": "Oportunidade de posicionamento em área estratégica ou inovadora",
                "estimated_value": estimated_value,
                "profit_potential": estimated_value * 0.25,
                "success_probability": 0.6,
                "opportunity_score": 80,
                "priority": "alta",
                "competitive_advantage": "Diferenciação técnica e capacidade de inovação"
            })
        
        # Low competition opportunities
        risks = risk_analysis.get("risks", [])
        high_complexity_risks = [r for r in risks if r.get("risk_type") == "técnico" and r.get("severity") in ["alta", "crítica"]]
        
        if len(high_complexity_risks) >= 2:
            opportunities.append({
                "opportunity_type": "estratégica",
                "title": "Baixa Concorrência por Complexidade",
                "description": "Oportunidade com potencial baixa concorrência devido à alta complexidade técnica",
                "estimated_value": estimated_value,
                "profit_potential": estimated_value * 0.30,
                "success_probability": 0.7,
                "opportunity_score": 85,
                "priority": "crítica",
                "competitive_advantage": "Expertise técnica especializada reduz número de competidores"
            })
        
        # Geographic opportunities
        geographic_reach = self._analyze_geographic_opportunity(description)
        if geographic_reach:
            opportunities.append(geographic_reach)
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
        
        logger.info(f"Identified {len(opportunities)} business opportunities")
        return opportunities
    
    def _analyze_text_risks(self, text: str) -> List[Dict[str, Any]]:
        """Analyze risks based on document text patterns"""
        risks = []
        text_lower = text.lower()
        
        for pattern in self.risk_patterns:
            for keyword in pattern.keywords:
                if keyword in text_lower:
                    # Calculate context-adjusted probability and impact
                    context = self._extract_context(text, keyword)
                    adjusted_prob, adjusted_impact = self._adjust_risk_scores(
                        pattern.base_probability, 
                        pattern.base_impact, 
                        context
                    )
                    
                    risk = {
                        "risk_type": pattern.risk_type.value,
                        "category": self._categorize_risk(keyword, context),
                        "title": f"Risco de {keyword}",
                        "description": pattern.description_template.format(keyword=keyword),
                        "probability": adjusted_prob,
                        "impact": adjusted_impact,
                        "risk_score": adjusted_prob * adjusted_impact,
                        "severity": self._calculate_severity(adjusted_prob * adjusted_impact),
                        "mitigation_strategy": pattern.mitigation_template.format(keyword=keyword),
                        "source_text": context,
                        "confidence": 0.8,
                        "keywords": [keyword]
                    }
                    
                    risks.append(risk)
        
        return risks
    
    def _analyze_structured_risks(self, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze risks based on structured data"""
        risks = []
        
        # Timeline risks
        opening_date = structured_data.get("data_abertura")
        if opening_date:
            days_until_opening = self._calculate_days_until(opening_date)
            if days_until_opening < 7:
                risks.append({
                    "risk_type": "operacional",
                    "category": "prazo",
                    "title": "Prazo Curto para Preparação",
                    "description": f"Apenas {days_until_opening} dias até a abertura da licitação",
                    "probability": 0.8,
                    "impact": 0.6,
                    "risk_score": 0.48,
                    "severity": "alta",
                    "mitigation_strategy": "Priorizar preparação da documentação e proposta",
                    "confidence": 0.9
                })
        
        # Value-based risks
        estimated_value = structured_data.get("valor_estimado", 0)
        if estimated_value > 10000000:  # > R$ 10M
            risks.append({
                "risk_type": "comercial",
                "category": "competição",
                "title": "Alta Competição por Valor Elevado",
                "description": f"Valor estimado de R$ {estimated_value:,.2f} pode atrair muitos concorrentes",
                "probability": 0.9,
                "impact": 0.7,
                "risk_score": 0.63,
                "severity": "alta",
                "mitigation_strategy": "Estratégia de preço competitiva e diferenciação técnica",
                "confidence": 0.8
            })
        
        return risks
    
    def _analyze_table_risks(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze risks based on table content"""
        risks = []
        
        for table in tables:
            if table.get("is_product_table"):
                products = table.get("products", [])
                
                # Complex specification risks
                complex_items = [p for p in products if self._is_complex_item(p)]
                if len(complex_items) > len(products) * 0.3:  # >30% complex items
                    risks.append({
                        "risk_type": "técnico",
                        "category": "especificação",
                        "title": "Especificações Técnicas Complexas",
                        "description": f"{len(complex_items)} itens com especificações técnicas complexas",
                        "probability": 0.6,
                        "impact": 0.7,
                        "risk_score": 0.42,
                        "severity": "média",
                        "mitigation_strategy": "Revisar especificações técnicas com equipe especializada",
                        "confidence": 0.7
                    })
                
                # High-value item risks
                high_value_items = [p for p in products if p.get("total_price", 0) > 100000]
                if high_value_items:
                    risks.append({
                        "risk_type": "financeiro",
                        "category": "valor",
                        "title": "Itens de Alto Valor Individual",
                        "description": f"{len(high_value_items)} itens com valor individual acima de R$ 100.000",
                        "probability": 0.5,
                        "impact": 0.8,
                        "risk_score": 0.40,
                        "severity": "média",
                        "mitigation_strategy": "Análise detalhada de custos para itens de alto valor",
                        "confidence": 0.8
                    })
        
        return risks
    
    def _analyze_deadline_risks(self, text: str, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze deadline and timeline related risks"""
        risks = []
        
        # Extract deadline patterns
        deadline_patterns = [
            r"prazo de (\d+) dias",
            r"entrega em (\d+) dias",
            r"até (\d{1,2}/\d{1,2}/\d{4})",
            r"data limite.*?(\d{1,2}/\d{1,2}/\d{4})"
        ]
        
        for pattern in deadline_patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                context = text[max(0, match.start()-100):match.end()+100]
                
                # Determine if this is a tight deadline
                if "dias" in match.group():
                    days = int(re.search(r'\d+', match.group()).group())
                    if days < 30:
                        risks.append({
                            "risk_type": "operacional",
                            "category": "prazo",
                            "title": f"Prazo Apertado de {days} Dias",
                            "description": f"Prazo de apenas {days} dias pode ser desafiador",
                            "probability": min(0.9, 1.0 - (days / 30)),
                            "impact": 0.6,
                            "risk_score": min(0.9, 1.0 - (days / 30)) * 0.6,
                            "severity": "alta" if days < 15 else "média",
                            "mitigation_strategy": "Planejar recursos dedicados para cumprir prazo",
                            "source_text": context,
                            "confidence": 0.8
                        })
        
        return risks
    
    def _analyze_competition_risks(self, text: str, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze competition-related risks"""
        risks = []
        
        # High competition indicators
        competition_keywords = [
            "menor preço", "maior desconto", "lance mínimo", 
            "proposta mais vantajosa", "melhor técnica e preço"
        ]
        
        for keyword in competition_keywords:
            if keyword in text.lower():
                risks.append({
                    "risk_type": "comercial",
                    "category": "competição",
                    "title": f"Alta Competição por {keyword.title()}",
                    "description": f"Critério de {keyword} indica alta competitividade",
                    "probability": 0.8,
                    "impact": 0.5,
                    "risk_score": 0.40,
                    "severity": "média",
                    "mitigation_strategy": "Otimizar custos e considerar diferenciação qualitativa",
                    "confidence": 0.7
                })
        
        return risks
    
    def _extract_context(self, text: str, keyword: str, window: int = 150) -> str:
        """Extract context around a keyword"""
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        pos = text_lower.find(keyword_lower)
        if pos == -1:
            return ""
        
        start = max(0, pos - window)
        end = min(len(text), pos + len(keyword) + window)
        
        return text[start:end].strip()
    
    def _adjust_risk_scores(self, base_prob: float, base_impact: float, context: str) -> Tuple[float, float]:
        """Adjust risk scores based on context"""
        prob_multiplier = 1.0
        impact_multiplier = 1.0
        
        # Context-based adjustments
        urgency_keywords = ["urgente", "emergencial", "imediato", "prioritário"]
        if any(keyword in context.lower() for keyword in urgency_keywords):
            prob_multiplier *= 1.3
            impact_multiplier *= 1.2
        
        complexity_keywords = ["complexo", "especializado", "específico", "técnico"]
        if any(keyword in context.lower() for keyword in complexity_keywords):
            prob_multiplier *= 1.2
            impact_multiplier *= 1.1
        
        return (
            min(1.0, base_prob * prob_multiplier),
            min(1.0, base_impact * impact_multiplier)
        )
    
    def _categorize_risk(self, keyword: str, context: str) -> str:
        """Categorize risk based on keyword and context"""
        categories = {
            "prazo": ["prazo", "cronograma", "data", "entrega"],
            "técnico": ["técnico", "especificação", "norma", "certificação"],
            "financeiro": ["pagamento", "preço", "custo", "financeiro"],
            "legal": ["legal", "documentação", "habilitação", "fiscal"],
            "operacional": ["operação", "logística", "fornecimento", "capacidade"]
        }
        
        keyword_lower = keyword.lower()
        context_lower = context.lower()
        
        for category, words in categories.items():
            if any(word in keyword_lower or word in context_lower for word in words):
                return category
        
        return "geral"
    
    def _calculate_severity(self, risk_score: float) -> str:
        """Calculate risk severity based on score"""
        if risk_score >= 0.8:
            return "crítica"
        elif risk_score >= 0.6:
            return "alta"
        elif risk_score >= 0.3:
            return "média"
        else:
            return "baixa"
    
    def _deduplicate_risks(self, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate or very similar risks"""
        if len(risks) <= 1:
            return risks
        
        unique_risks = []
        
        for risk in risks:
            is_duplicate = False
            
            for existing in unique_risks:
                similarity = self._calculate_risk_similarity(risk, existing)
                
                if similarity > 0.7:  # High similarity threshold
                    is_duplicate = True
                    
                    # Keep the one with higher risk score
                    if risk.get("risk_score", 0) > existing.get("risk_score", 0):
                        unique_risks.remove(existing)
                        unique_risks.append(risk)
                    break
            
            if not is_duplicate:
                unique_risks.append(risk)
        
        return unique_risks
    
    def _calculate_risk_similarity(self, risk1: Dict[str, Any], risk2: Dict[str, Any]) -> float:
        """Calculate similarity between two risks"""
        # Compare titles
        title_sim = 0.0
        if risk1.get("title") and risk2.get("title"):
            title1_words = set(risk1["title"].lower().split())
            title2_words = set(risk2["title"].lower().split())
            
            if title1_words or title2_words:
                intersection = len(title1_words.intersection(title2_words))
                union = len(title1_words.union(title2_words))
                title_sim = intersection / union if union > 0 else 0
        
        # Compare categories and types
        type_sim = 1.0 if risk1.get("risk_type") == risk2.get("risk_type") else 0.0
        cat_sim = 1.0 if risk1.get("category") == risk2.get("category") else 0.0
        
        # Weighted average
        return (title_sim * 0.5) + (type_sim * 0.3) + (cat_sim * 0.2)
    
    def _prioritize_risks(self, risks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort risks by priority (risk score and severity)"""
        severity_weights = {"crítica": 4, "alta": 3, "média": 2, "baixa": 1}
        
        def risk_priority(risk):
            severity = risk.get("severity", "baixa")
            risk_score = risk.get("risk_score", 0)
            confidence = risk.get("confidence", 0)
            
            return (severity_weights.get(severity, 1) * risk_score * confidence)
        
        return sorted(risks, key=risk_priority, reverse=True)
    
    def _calculate_risk_summary(self, risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall risk assessment summary"""
        if not risks:
            return {"overall_risk_level": "baixo", "total_score": 0}
        
        # Count by severity
        severity_counts = {"crítica": 0, "alta": 0, "média": 0, "baixa": 0}
        total_score = 0
        
        for risk in risks:
            severity = risk.get("severity", "baixa")
            severity_counts[severity] += 1
            total_score += risk.get("risk_score", 0)
        
        avg_score = total_score / len(risks)
        
        # Determine overall risk level
        if severity_counts["crítica"] >= 3 or avg_score >= 0.7:
            overall_level = "crítico"
        elif severity_counts["crítica"] >= 1 or severity_counts["alta"] >= 3 or avg_score >= 0.5:
            overall_level = "alto"
        elif severity_counts["alta"] >= 1 or severity_counts["média"] >= 3 or avg_score >= 0.3:
            overall_level = "médio"
        else:
            overall_level = "baixo"
        
        return {
            "overall_risk_level": overall_level,
            "total_score": round(total_score, 2),
            "average_score": round(avg_score, 2),
            "severity_distribution": severity_counts,
            "risk_count": len(risks),
            "top_risk_types": self._get_top_risk_types(risks)
        }
    
    def _get_top_risk_types(self, risks: List[Dict[str, Any]]) -> List[Dict[str, int]]:
        """Get most common risk types"""
        type_counts = {}
        
        for risk in risks:
            risk_type = risk.get("risk_type", "unknown")
            type_counts[risk_type] = type_counts.get(risk_type, 0) + 1
        
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"type": t, "count": c} for t, c in sorted_types[:5]]
    
    def _calculate_days_until(self, date_str: str) -> int:
        """Calculate days until a given date"""
        try:
            # Try different date formats
            date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
            
            target_date = None
            for fmt in date_formats:
                try:
                    target_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            
            if target_date:
                delta = target_date - datetime.now()
                return max(0, delta.days)
                
        except Exception:
            pass
        
        return 999  # Return high number if can't parse
    
    def _is_complex_item(self, product: Dict[str, Any]) -> bool:
        """Determine if a product item is technically complex"""
        description = product.get("description", "").lower()
        
        complex_keywords = [
            "especificação técnica", "norma", "certificação", "homologação",
            "instalação", "configuração", "integração", "customização",
            "software", "sistema", "equipamento especializado"
        ]
        
        return any(keyword in description for keyword in complex_keywords)
    
    def _analyze_geographic_opportunity(self, description: str) -> Optional[Dict[str, Any]]:
        """Analyze geographic expansion opportunities"""
        state_capitals = [
            "brasília", "são paulo", "rio de janeiro", "belo horizonte",
            "salvador", "fortaleza", "recife", "porto alegre", "curitiba"
        ]
        
        description_lower = description.lower()
        
        for capital in state_capitals:
            if capital in description_lower:
                return {
                    "opportunity_type": "geográfica",
                    "title": f"Expansão Geográfica - {capital.title()}",
                    "description": f"Oportunidade de expansão ou fortalecimento na região de {capital.title()}",
                    "estimated_value": 0,  # Will be filled by main analysis
                    "profit_potential": 0,
                    "success_probability": 0.4,
                    "opportunity_score": 60,
                    "priority": "média",
                    "competitive_advantage": "Presença local ou parcerias regionais estratégicas"
                }
        
        return None