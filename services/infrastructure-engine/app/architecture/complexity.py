def calculate_complexity(model) -> int:
    """
    Calculates a deterministic complexity score based on the ArchitectureModel.
    Do NOT use AI.
    """
    score = 0
    
    # 1. Languages and Frameworks (base score)
    score += len(model.application.languages) * 2
    score += len(model.application.frameworks) * 3
    
    # 2. Infrastructure Components
    if model.infrastructure.docker:
        score += 2
    if model.infrastructure.compose:
        score += 3
    if model.infrastructure.kubernetes:
        score += 10
    if model.infrastructure.terraform:
        score += 5
    if model.infrastructure.helm:
        score += 4
    if model.infrastructure.pulumi:
        score += 5
    if model.infrastructure.ansible:
        score += 4
        
    # 3. Services
    score += len(model.services) * 3
    score += len(model.databases) * 4
    score += len(model.caches) * 2
    score += len(model.queues) * 3
    
    # 4. Gaps
    # Gaps represent tech debt, adding to cognitive load/complexity
    score += len(model.gaps) * 2
    
    return score
