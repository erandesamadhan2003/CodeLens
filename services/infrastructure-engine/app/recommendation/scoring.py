from app.architecture.models import ArchitectureModel
from typing import Dict

def calculate_scores(arch: ArchitectureModel, findings: list) -> Dict[str, int]:
    scores = {
        "security_score": 100,
        "reliability_score": 100,
        "scalability_score": 100,
        "deployment_score": 100,
        "maintainability_score": 100,
        "cost_score": 100
    }
    
    # 1. Deduct based on findings
    # CRITICAL = -15, HIGH = -10, MEDIUM = -5, LOW = -2
    for finding in findings:
        deduction = 0
        if finding.severity == "CRITICAL":
            deduction = 15
        elif finding.severity == "HIGH":
            deduction = 10
        elif finding.severity == "MEDIUM":
            deduction = 5
        elif finding.severity == "LOW":
            deduction = 2
            
        category = finding.category.lower()
        if category == "security":
            scores["security_score"] -= deduction
        elif category == "reliability":
            scores["reliability_score"] -= deduction
        elif category == "performance" or category == "scalability":
            scores["scalability_score"] -= deduction
        elif category == "cost":
            scores["cost_score"] -= deduction
        else:
            # Default fallback
            scores["maintainability_score"] -= deduction
            
    # 2. Deduct based on architectural gaps
    gaps = arch.gaps
    if "containerization" in gaps:
        scores["scalability_score"] -= 20
        scores["deployment_score"] -= 20
    if "deployment" in gaps:
        scores["deployment_score"] -= 30
    if "infrastructure_as_code" in gaps:
        scores["maintainability_score"] -= 20
        
    # Complexity penalty
    if arch.complexity > 50:
        scores["maintainability_score"] -= 10
        
    # Cap scores at 0
    for key in scores:
        scores[key] = max(0, scores[key])
        
    # Calculate overall score (average of the 6 dimensions)
    overall = sum(scores.values()) // 6
    scores["overall_score"] = overall
    
    return scores
