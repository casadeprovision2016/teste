# app/services/risk_analyzer_basic.py
"""
Basic risk analyzer with simplified dependencies
"""
import logging
import re
from typing import Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskAnalyzer:
    """Basic risk analysis without heavy ML dependencies"""
    
    def __init__(self):
        self.risk_patterns = self._load_risk_patterns()
        logger.info("Basic Risk Analyzer initialized")
    
    def _load_risk_patterns(self) -> Dict[str, List[str]]:
        """Load basic risk patterns for Brazilian procurement"""
        return {
            "high_risk": [
                "urgente", "emergencial", "dispensa", "inexigibilidade",
                "prazo reduzido", "aditivo", "prorrogação"
            ],
            "financial_risk": [
                "pagamento antecipado", "sem garantia", "valor elevado",
                "orçamento limitado", "reajuste automático"
            ],
            "technical_risk": [
                "especificação única", "marca específica", "tecnologia proprietária",
                "sem similar", "exclusivo", "único fornecedor"
            ],
            "timeline_risk": [
                "prazo exíguo", "entrega imediata", "cronograma apertado",
                "prazo reduzido", "urgência"
            ],
            "regulatory_risk": [
                "alteração normativa", "mudança regulatória", "nova lei",
                "decreto pendente", "norma em revisão"
            ]
        }
    
    def analyze_risks(self, text: str, edital_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze risks in the edital text"""
        try:
            logger.info("Analyzing risks in edital text")
            
            risks = {
                "overall_risk_level": "medium",
                "risk_score": 0.5,
                "identified_risks": [],
                "risk_categories": {
                    "technical": {"level": "low", "factors": []},
                    "financial": {"level": "low", "factors": []},
                    "timeline": {"level": "low", "factors": []},
                    "regulatory": {"level": "low", "factors": []},
                },
                "recommendations": []
            }
            
            text_lower = text.lower()
            total_risk_score = 0
            risk_count = 0
            
            # Check each risk category
            for category, patterns in self.risk_patterns.items():
                if category == "high_risk":
                    continue
                    
                found_patterns = []
                category_score = 0
                
                for pattern in patterns:
                    if pattern in text_lower:
                        found_patterns.append(pattern)
                        category_score += 1
                        risk_count += 1
                
                # Calculate category risk level
                if category_score >= 3:
                    level = "high"
                    score = 0.8
                elif category_score >= 1:
                    level = "medium" 
                    score = 0.5
                else:
                    level = "low"
                    score = 0.2
                
                category_key = category.replace("_risk", "")
                risks["risk_categories"][category_key] = {
                    "level": level,
                    "score": score,
                    "factors": found_patterns
                }
                
                total_risk_score += score
            
            # Check for high-risk indicators
            high_risk_count = 0
            for pattern in self.risk_patterns["high_risk"]:
                if pattern in text_lower:
                    risks["identified_risks"].append({
                        "type": "high_priority",
                        "description": f"High-risk indicator found: {pattern}",
                        "severity": "high"
                    })
                    high_risk_count += 1
            
            # Calculate overall risk
            avg_category_score = total_risk_score / 4 if total_risk_score > 0 else 0.2
            high_risk_bonus = min(high_risk_count * 0.2, 0.4)
            final_score = min(avg_category_score + high_risk_bonus, 1.0)
            
            risks["risk_score"] = round(final_score, 2)
            
            if final_score >= 0.7:
                risks["overall_risk_level"] = "high"
            elif final_score >= 0.4:
                risks["overall_risk_level"] = "medium"
            else:
                risks["overall_risk_level"] = "low"
            
            # Add recommendations
            risks["recommendations"] = self._generate_recommendations(risks)
            
            logger.info(f"Risk analysis completed. Overall level: {risks['overall_risk_level']}")
            return risks
            
        except Exception as e:
            logger.error(f"Error in risk analysis: {e}")
            return {
                "overall_risk_level": "unknown",
                "risk_score": 0.5,
                "error": str(e),
                "identified_risks": [],
                "risk_categories": {},
                "recommendations": []
            }
    
    def _generate_recommendations(self, risks: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on identified risks"""
        recommendations = []
        
        risk_level = risks["overall_risk_level"]
        categories = risks["risk_categories"]
        
        if risk_level == "high":
            recommendations.append("Alto risco identificado - revisar cuidadosamente antes de participar")
        
        # Technical risks
        if categories.get("technical", {}).get("level") == "high":
            recommendations.append("Verificar capacidade técnica para atender especificações")
            recommendations.append("Avaliar necessidade de parcerias técnicas")
        
        # Financial risks
        if categories.get("financial", {}).get("level") == "high":
            recommendations.append("Avaliar impacto financeiro e fluxo de caixa")
            recommendations.append("Considerar garantias e seguros adicionais")
        
        # Timeline risks
        if categories.get("timeline", {}).get("level") == "high":
            recommendations.append("Verificar viabilidade do cronograma proposto")
            recommendations.append("Planejar recursos adicionais para prazos apertados")
        
        # Regulatory risks
        if categories.get("regulatory", {}).get("level") == "high":
            recommendations.append("Acompanhar mudanças regulatórias relevantes")
            recommendations.append("Consultar especialistas jurídicos")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Risco dentro do esperado - proceder com análise padrão")
        
        return recommendations
    
    def calculate_opportunity_score(self, edital_data: Dict[str, Any], company_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate business opportunity score"""
        try:
            opportunity = {
                "score": 0.5,
                "level": "medium",
                "factors": [],
                "estimated_competition": "medium",
                "recommendation": "avaliar"
            }
            
            # Basic scoring based on available data
            base_score = 0.5
            
            # Adjust based on risk level
            if edital_data.get("risk_level") == "low":
                base_score += 0.2
            elif edital_data.get("risk_level") == "high":
                base_score -= 0.2
            
            # Adjust based on value (if available)
            estimated_value = edital_data.get("estimated_value", 0)
            if estimated_value > 1000000:  # High value
                base_score += 0.1
                opportunity["factors"].append("Alto valor do contrato")
            
            opportunity["score"] = max(0.1, min(0.9, base_score))
            
            # Determine level
            if opportunity["score"] >= 0.7:
                opportunity["level"] = "high"
                opportunity["recommendation"] = "participar"
            elif opportunity["score"] >= 0.4:
                opportunity["level"] = "medium"  
                opportunity["recommendation"] = "avaliar"
            else:
                opportunity["level"] = "low"
                opportunity["recommendation"] = "evitar"
            
            return opportunity
            
        except Exception as e:
            logger.error(f"Error calculating opportunity score: {e}")
            return {
                "score": 0.5,
                "level": "unknown",
                "error": str(e),
                "factors": [],
                "recommendation": "revisar"
            }