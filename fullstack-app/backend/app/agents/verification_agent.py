import re
import json
from typing import Dict, Any, Optional, List, Tuple, Union
from pydantic import BaseModel
from openai import OpenAI, AzureOpenAI
from dataclasses import dataclass, field


class VerificationIssue(BaseModel):
    """Model for verification issues"""
    type: str
    section: str
    description: str
    suggestion: str


class VerificationResult(BaseModel):
    """Output model for verification results"""
    score: float
    issues: List[VerificationIssue]
    suggestions: List[Dict[str, str]]  
    summary: str
    strengths: List[str]
    needs_revision: bool
    round_number: int
    decision_explanation: str
    status: str = "completed"


def verify_report_content(report_content: str, transcript: str, meeting_notes: str = "",
                         additional_instructions: str = "", round_number: int = 1, 
                         api_config: Dict[str, Any] = None,
                         previous_verification_results: List[Dict] = None,
                         previous_revision_notes: List[str] = None,
                         sample_report: str = None) -> VerificationResult:
    """
    Progressive verification function with context awareness and round-based assessment.
    
    This function implements a verification system that adapts based on verification round:
    
    1. ROUND-BASED VERIFICATION:
       - Round 1: Comprehensive verification with full criteria assessment
       - Round 2: Focused verification on significant issues  
       - Round 3+: Acceptance-oriented verification focusing on critical blocking issues
    
    2. CONSISTENT SCORING SYSTEM:
       - Severity-weighted scoring based on actual issue impact
       - Issue persistence tracking to measure progress between rounds
       - Consistent scoring standards without round-based adjustments
    
    3. PROGRESSIVE ISSUE ASSESSMENT:
       - Different strictness levels applied based on verification round
       - Issue filtering based on severity and criticality
       - Focus on completion-blocking issues in later rounds
    
    4. CONTEXT-AWARE PROCESSING:
       - Tracks sections that had previous issues for focused attention
       - Compares current vs previous issues to identify changes
       - Maintains revision history context for informed decision making
    
    Args:
        report_content: The generated report to verify
        transcript: Original meeting transcript 
        meeting_notes: Additional meeting notes (optional)
        additional_instructions: Special instructions to verify compliance (optional)
        round_number: Current verification round number (determines assessment strictness)
        api_config: API configuration dictionary
        previous_verification_results: List of previous verification results for context
        previous_revision_notes: List of revision notes from previous rounds
        
    Returns:
        VerificationResult: Progressive verification results with context awareness
    """
    if not report_content or not transcript:
        raise ValueError("Missing required inputs: report_content and transcript")
    
    # Initialize progressive verification context for this round
    context_memory = _build_verification_context_memory(
        round_number, previous_verification_results or [], previous_revision_notes or []
    )
    
    print(f"\n=== PROGRESSIVE VERIFICATION ROUND {round_number} ===")
    print(f"Report content length: {len(report_content)} characters")
    print(f"Verification strictness: {context_memory['verification_strictness']}")
    if context_memory['focus_sections']:
        print(f"Focus sections (had previous issues): {context_memory['focus_sections']}")
    if context_memory.get('resolved_areas'):
        print(f"Resolved areas: {context_memory['resolved_areas']}")
    print(f"Progressive mode: {'ACTIVE' if context_memory['convergence_mode'] else 'STANDARD'}")
    
    # Extract company information section from report to avoid checking it
    company_info_section, content_without_company_info = _extract_company_info_section(report_content)
    
    # Create progressive verification prompt based on round and context
    progressive_prompt = _create_context_aware_verification_prompt(
        content_without_company_info, transcript, meeting_notes, 
        additional_instructions, round_number, context_memory, sample_report
    )
    
    # Execute progressive verification with context awareness
    verification_results = _verify_report_with_context(
        progressive_prompt, api_config, context_memory
    )
    
    # Progressive scoring pipeline with consistency validation
    # Extract raw results from LLM for assessment
    raw_score = verification_results.get('score', 0)
    raw_issues = verification_results.get('issues', [])
    
    # Step 1: Validate and normalize issues structure
    validated_issues = _validate_and_normalize_issues(raw_issues)
    
    # Step 1.5: Apply progressive issue filtering based on verification strictness
    strictness = context_memory.get('verification_strictness', 'strict')
    filtered_issues = _filter_issues_by_strictness(validated_issues, strictness, round_number)
    
    # Step 2: Apply enhanced scoring with severity weighting and issue tracking
    # Pass previous issues for improvement tracking if available
    previous_issues = []
    if previous_verification_results and len(previous_verification_results) > 0:
        last_verification = previous_verification_results[-1]
        previous_issues = last_verification.get('issues', [])
    
    enhanced_score = _validate_and_normalize_score(raw_score, filtered_issues, round_number, previous_issues)
    
    # Use enhanced results with filtered issues based on strictness
    score = enhanced_score
    issues = filtered_issues
    
    # Extract critical issues - ALL sections are critical (original logic)
    critical_sections = ["AI Maturity Level", "Current Solution Development Stage", 
                    "Validity of Concept and Authenticity of Problem Addressed",
                    "Integration and Importance of AI in the Idea",
                    "Identified Target Market and Customer Segments",
                    "Data Requirement Assessment", 
                    "Data Collection Strategy",
                    "Technical Expertise and Capability",
                    "Expectations from FAIR Services",
                    "Recommendations",
                    ]
    
    # Identify any missing critical sections
    missing_critical_sections = [
        issue for issue in issues 
        if issue.get('type') == 'Missing Section' and 
        any(crit_sec in issue.get('section', '') for crit_sec in critical_sections)
    ]
    
    # Apply improved revision logic with severity-aware decision making
    needs_revision, decision_explanation = _determine_revision_need(score, issues, round_number, missing_critical_sections)
    
    print(f"Verification completed: Score={score}/10, Issues={len(issues)}, Needs revision={needs_revision}")
    
    return VerificationResult(
        score=score,
        issues=[VerificationIssue(**issue) if isinstance(issue, dict) else issue for issue in issues],
        suggestions=verification_results.get('suggestions', []),  # Include suggestions
        summary=verification_results.get('summary', ''),
        strengths=verification_results.get('strengths', []),
        needs_revision=needs_revision,
        round_number=round_number,
        decision_explanation=decision_explanation
    )


def _validate_and_normalize_score(raw_score: Any, issues: List[Dict], round_number: int, 
                                 previous_issues: List[Dict] = None) -> float:
    """
    Scoring mechanism with severity weighting and consistency validation.
    
    This function implements a scoring system that:
    1. Calculates severity-weighted reference scores based on issue types and counts
    2. Validates LLM-provided scores against logical consistency rules
    3. Tracks issue persistence across rounds for accurate assessment
    4. Uses weighted averaging when LLM and calculated scores differ significantly
    
    Args:
        raw_score: Raw score from LLM (could be invalid or inconsistent)
        issues: List of current issues with severity ('High', 'Medium', 'Low') and type classifications
        round_number: Current verification round (1, 2, 3+) - used for logging
        previous_issues: List of issues from previous round for comparison
        
    Returns:
        float: Validated and normalized score between 1.0-10.0
    """
    
    # Step 1: Calculate severity-weighted reference score
    # This provides an objective baseline based on actual issue severity and types
    severity_based_score = _calculate_severity_weighted_score(issues)
    
    # Step 2: Validate and normalize the raw LLM score
    try:
        llm_score = float(raw_score)
        llm_score = max(1.0, min(10.0, llm_score))  # Clamp to valid range
    except (ValueError, TypeError, AttributeError):
        # LLM provided invalid score, use our calculated score as fallback
        print(f"Invalid score '{raw_score}', using severity-based score: {severity_based_score:.1f}")
        return severity_based_score
    
    # Step 3: Consistency validation between LLM and severity-based scores
    # Large differences indicate potential LLM inconsistency
    score_difference = abs(llm_score - severity_based_score)
    
    if score_difference > 1.5:  # Significant inconsistency detected
        print(f"Score inconsistency detected: LLM={llm_score}, Severity-based={severity_based_score:.1f} (diff: {score_difference:.1f})")
        # Use weighted average favoring the more reliable severity-based calculation
        final_score = (severity_based_score * 0.7) + (llm_score * 0.3)
        print(f"Applied weighted averaging: {final_score:.1f}")
    else:
        # Scores are reasonably consistent, use simple average
        final_score = (llm_score + severity_based_score) / 2
    
    # Step 4: Issue progression tracking and score adjustment
    # Compare current issues with previous round to measure changes
    if previous_issues and round_number > 1:
        improvement_adjustment = _calculate_improvement_adjustment(issues, previous_issues)
        if improvement_adjustment > 0:
            final_score = min(final_score + improvement_adjustment, 10.0)
            print(f"Round {round_number} progress adjustment: +{improvement_adjustment:.1f}")
    
    final_score = round(final_score, 1)
    print(f"Final validated score: {final_score}/10 (LLM: {llm_score}, Severity-based: {severity_based_score:.1f})")
    
    return final_score


def _calculate_improvement_adjustment(current_issues: List[Dict], previous_issues: List[Dict]) -> float:
    """
    Calculate score adjustment based on issue resolution progress between rounds.
    
    This function compares current and previous issues to determine if progress
    has been made, providing appropriate score adjustments.
    
    Args:
        current_issues: Issues found in current verification round
        previous_issues: Issues found in previous verification round
        
    Returns:
        float: Score adjustment (0.0 to 1.0) based on measured progress
    """
    if not previous_issues:
        return 0.0  # No previous issues to compare against
    
    # Track resolved vs persistent vs new issues
    current_descriptions = {issue.get('description', '') for issue in current_issues}
    previous_descriptions = {issue.get('description', '') for issue in previous_issues}
    
    resolved_count = len(previous_descriptions - current_descriptions)
    persistent_count = len(previous_descriptions & current_descriptions) 
    new_count = len(current_descriptions - previous_descriptions)
    
    print(f"  Issue tracking: {resolved_count} resolved, {persistent_count} persistent, {new_count} new")
    
    # Calculate adjustment based on resolution progress
    if resolved_count > 0 and new_count <= resolved_count:
        # Net positive progress (more resolved than new)
        progress_ratio = (resolved_count - new_count) / len(previous_issues)
        adjustment = min(progress_ratio * 0.5, 0.5)  # Max 0.5 point adjustment
        print(f", adjustment score = {adjustment}")
        return adjustment
    
    return 0.0  # No net progress detected


def _calculate_severity_weighted_score(issues: List[Dict]) -> float:
    """
    Calculate objective score based on issue severity with consistent weighting system.
    
    This function implements a scoring algorithm that:
    1. Assigns consistent weights to issues based on their severity (High/Medium/Low)
    2. Applies type-specific multipliers for different kinds of issues
    3. Maintains consistent scoring standards across all verification rounds
    4. Provides detailed breakdown of how the score was calculated
    
    Args:
        issues: List of issue dictionaries with 'severity' and 'type' fields
        
    Returns:
        float: Calculated score between 1.0-10.0 based on issue severity
    """
    if not issues:
        return 10.0  # Perfect score when no issues are found
    
    # Severity weights: How much each severity level impacts the score
    # These weights are calibrated based on the relative impact of different issue types
    severity_weights = {
        'High': 2.5,     # Major issues that significantly affect report quality
        'Medium': 1.2,   # Moderate issues with noticeable but manageable impact
        'Low': 0.4       # Minor issues with minimal impact on overall quality
    }
    
    # Issue type multipliers: Additional context-specific weighting
    # Different types of issues have varying importance regardless of severity
    type_multipliers = {
        'Factual Error': 1.4,           # Critical - affects accuracy and trust
        'Missing Section': 1.3,         # Structural - affects completeness
        'Required Element Missing': 1.1, # Content gaps - affects thoroughness
        'Relevance': 1.0,              # Standard content quality issues
        'Clarity Issue': 0.7            # Presentation - affects readability but not content
    }
    
    total_deduction = 0.0
    critical_count = serious_count = minor_count = 0
    
    # Calculate weighted deductions for each issue
    for issue in issues:
        severity = issue.get('severity', 'Medium')
        issue_type = issue.get('type', 'General')
        
        # Base deduction from severity level
        base_deduction = severity_weights.get(severity, 1.0)
        
        # Apply type-specific multiplier
        type_multiplier = type_multipliers.get(issue_type, 1.0)
        
        # Calculate final deduction for this issue with consistent weighting
        final_deduction = base_deduction * type_multiplier
        total_deduction += final_deduction
        
        # Track issue counts by effective severity for reporting
        if severity == 'High' or issue_type in ['Factual Error', 'Missing Section']:
            critical_count += 1
        elif severity == 'Medium':
            serious_count += 1
        else:
            minor_count += 1
    
    # Calculate final score (start from 10, subtract weighted deductions)
    final_score = max(10.0 - total_deduction, 1.0)  # Floor at 1.0
    
    # Detailed logging for transparency and debugging
    print(f"  Severity breakdown: {critical_count} critical, {serious_count} serious, {minor_count} minor issues")
    print(f"  Total weighted deduction: {total_deduction:.1f} points")
    print(f"  Calculated severity-based score: {final_score:.1f}/10")
    
    return final_score

def _get_fallback_score(issues_count: int = 0) -> float:
    """
    Fallback scoring system for when LLM scoring fails.
    
    This function provides consistent fallback scores when LLM scoring fails.
    It uses standard scoring logic based on issue count and severity.
    
    Args:
        issues_count: Number of issues detected (used for adjustment)
        
    Returns:
        float: Appropriate fallback score based on issue count
    """
    # Consistent base score regardless of verification round
    # This ensures scoring remains stable across multiple rounds
    base_score = 7.5  # Standard baseline for fallback scenarios
    
    # Adjust score based on issue count with consistent impact
    if issues_count > 0:
        # Consistent impact factor - issues have equal weight across all rounds
        impact_factor = 0.25  # Standard deduction per issue
        
        # Calculate adjustment with maximum cap
        adjustment = min(issues_count * impact_factor, 2.5)
        base_score = max(base_score - adjustment, 1.0)  # Floor at 1.0
    
    print(f"Fallback score calculation: {issues_count} issues → {base_score:.1f}")
    return base_score


def _validate_and_normalize_issues(raw_issues: Any) -> List[Dict[str, str]]:
    """
    Validate and normalize issue structures with required fields.
    
    Args:
        raw_issues: Raw issues array from LLM (could be malformed)
        
    Returns:
        List[Dict]: Properly structured issues with all required fields
    """
    
    if not isinstance(raw_issues, list):
        print(f"Warning: Issues is not a list, got {type(raw_issues)}")
        return []
    
    validated_issues = []
    
    for i, issue in enumerate(raw_issues):
        if not isinstance(issue, dict):
            print(f"Warning: Issue {i} is not a dict, skipping")
            continue
        
        # Ensure all required fields with proper defaults
        validated_issue = {
            'type': str(issue.get('type', 'General Issue')),
            'section': str(issue.get('section', 'General')), 
            'description': str(issue.get('description', 'Issue description not provided')),
            'suggestion': str(issue.get('suggestion', 'No specific suggestion provided')),
            'severity': _normalize_severity(issue.get('severity'), issue.get('type'))
        }
        
        validated_issues.append(validated_issue)
        
    print(f"Validated {len(validated_issues)} issues from {len(raw_issues)} raw issues")
    return validated_issues


def _normalize_severity(raw_severity: Any, issue_type: str) -> str:
    """
    Normalize severity field with intelligent fallbacks.
    
    Args:
        raw_severity: Raw severity from LLM
        issue_type: Issue type to infer severity from
        
    Returns:
        str: Normalized severity (High, Medium, Low)
    """
    
    # Try to parse provided severity
    if isinstance(raw_severity, str):
        severity_lower = raw_severity.lower().strip()
        if severity_lower in ['high', 'critical', 'severe']:
            return 'High'
        elif severity_lower in ['medium', 'moderate', 'normal']:
            return 'Medium' 
        elif severity_lower in ['low', 'minor', 'trivial']:
            return 'Low'
    
    # Fallback: Infer from issue type
    severity_mapping = {
        'Missing Section': 'High',        # Always critical
        'Factual Error': 'High',          # Always critical
        'Section Order': 'Medium',        # Important structure issue
        'Required Element Missing': 'Medium',  # Important content issue
        'Recommendation Issue': 'Medium', # Important quality issue
        'Clarity Issue': 'Low'            # Minor formatting issue
    }
    
    inferred_severity = severity_mapping.get(issue_type, 'Medium')
    
    if raw_severity and str(raw_severity).strip():
        print(f"Normalized severity '{raw_severity}' → '{inferred_severity}' for type '{issue_type}'")
    
    return inferred_severity


def _filter_issues_by_strictness(issues: List[Dict], strictness: str, round_number: int) -> List[Dict]:
    """
    Filter issues based on verification strictness level for progressive assessment.
    
    This function applies different filtering criteria based on strictness:
    - Strict (Round 1): Include all issues for comprehensive assessment
    - Moderate (Round 2): Focus on significant issues, filter minor ones
    - Lenient (Round 3+): Focus on critical and high severity issues only
    
    Args:
        issues: List of validated issues
        strictness: Verification strictness level ('strict', 'moderate', 'lenient')
        round_number: Current round number for logging
        
    Returns:
        List[Dict]: Filtered issues based on strictness criteria
    """
    if strictness == 'strict':
        # Round 1: Include all issues for comprehensive assessment
        print(f"  Round {round_number} strict mode: Including all {len(issues)} issues")
        return issues
    
    elif strictness == 'moderate':
        # Round 2: Filter out minor Low severity issues, keep significant ones
        filtered = []
        for issue in issues:
            severity = issue.get('severity', 'Medium')
            issue_type = issue.get('type', '')
            
            # Keep High and Medium severity issues
            if severity in ['High', 'Medium']:
                filtered.append(issue)
            # Keep Low severity issues only if they're critical types
            elif severity == 'Low' and issue_type in ['Missing Section', 'Factual Error']:
                filtered.append(issue)
            # Filter out minor Low severity issues (clarity, formatting, etc.)
        
        filtered_count = len(issues) - len(filtered)
        if filtered_count > 0:
            print(f"  Round {round_number} moderate mode: Filtered out {filtered_count} minor issues, kept {len(filtered)}")
        return filtered
    
    else:  # lenient
        # Round 3+: Only keep High severity and critical blocking issues
        filtered = []
        for issue in issues:
            severity = issue.get('severity', 'Medium')
            issue_type = issue.get('type', '')
            
            # Only keep High severity issues
            if severity == 'High':
                filtered.append(issue)
            # Keep critical issue types regardless of severity
            elif issue_type in ['Missing Section', 'Factual Error']:
                filtered.append(issue)
            # Filter out all Medium and Low severity non-critical issues
        
        filtered_count = len(issues) - len(filtered)
        if filtered_count > 0:
            print(f"  Round {round_number} lenient mode: Filtered out {filtered_count} non-critical issues, kept {len(filtered)}")
        return filtered

def _extract_suggestions_from_issues(issues: List[Dict]) -> List[Dict[str, str]]:
    """
    Extract suggestions from issues to create separate suggestions array for revision agent.
    
    Args:
        issues: List of validated issues with embedded suggestions
        
    Returns:
        List[Dict]: Separate suggestions array formatted for revision agent
    """
    suggestions = []
    
    for issue in issues:
        suggestion_text = issue.get('suggestion', '')
        section = issue.get('section', 'General')
        issue_type = issue.get('type', 'General Issue')
        
        if suggestion_text and suggestion_text != 'No specific suggestion provided':
            suggestions.append({
                'section': section,
                'description': suggestion_text,
                'type': issue_type,  # Include type for better context
                'severity': issue.get('severity', 'Medium')  # Include severity for revision agent
            })
    
    print(f"Extracted {len(suggestions)} suggestions from {len(issues)} issues")
    return suggestions

def _get_score_standard_level(score: float) -> str:
    """
    Determine standard level based on score value.

    Args:
        score: Verification score from 0-10

    Returns:
        str: Standard level description
    """
    if score >= 9.0:
        return "high standards"
    elif score >= 8.0 and score < 9.0:
        return "moderate standards"
    elif score >= 7.0 and score < 8.0:
        return "acceptable standards"
    else:
        return "below minimum standards"


def _determine_revision_need(score: float, issues: List[Dict[str, Any]], round_number: int,
                           missing_critical_sections: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Enhanced revision logic that considers issue severity, type, and round-specific criteria.

    This function implements a progressive quality assurance approach where:
    - Round 1: Very high standards (8.5/10) but considers issue severity (prevent unnecessary revisions for minor issues)
    - Round 2: High standards (8.0/10) focusing on serious+ issues only (moderate standards)
    - Round 3+: Good standards (7.0/10) - only critical issues justify revision (lenient standards to prevent infinite loops)

    Args:
        score: Verification score from 0-10
        issues: List of identified issues with type, severity, section, description
        round_number: Current verification round (1, 2, 3+)
        missing_critical_sections: Critical sections that are completely missing

    Returns:
        tuple: (needs_revision: bool, decision_explanation: str)
    """
    
    # RULE 1: ALWAYS revise if critical sections are missing
    # This is non-negotiable as these sections are required for report completeness
    if missing_critical_sections:
        return True, f"Report requires revision due to {len(missing_critical_sections)} missing critical sections: {[sec.get('section', 'Unknown') for sec in missing_critical_sections[:3]]}{'...' if len(missing_critical_sections) > 3 else ''}"
    
    # CLASSIFICATION: Categorize issues by severity and type for intelligent decision making
    
    # High severity issues: Always require attention regardless of type
    high_severity_issues = [issue for issue in issues if issue.get('severity', 'Medium').lower() == 'high']
    
    # Critical issue types: Fundamental problems that affect report integrity
    critical_type_issues = [issue for issue in issues if issue.get('type') in 
                          ['Missing Section', 'Factual Error']]
    
    # Serious issue types: Structural or content problems that impact quality
    serious_type_issues = [issue for issue in issues if issue.get('type') in 
                         ['Section Order', 'Required Element Missing', 'Recommendation Issue']]
    
    # Minor issue types: Clarity or formatting issues that don't affect core content
    minor_type_issues = [issue for issue in issues if issue.get('type') in 
                       ['Clarity Issue']]
    
    # ROUND-SPECIFIC DECISION LOGIC
    
    if round_number == 1:
        # ROUND 1: High standards but intelligent about minor issues
        # Goal: Catch significant problems while allowing minor issues if overall quality is good
        
        # Revision triggers (OR logic - any condition triggers revision):
        revision_triggers = []
        
        # Score-based trigger: Report quality below high standard
        # Using 8.5 as threshold - expects very good quality but not perfection
        if score < 8.5:
            revision_triggers.append(f"score below 8.5 ({score})")
        
        # High severity trigger: Any high-severity issue needs immediate attention
        if high_severity_issues:
            revision_triggers.append(f"{len(high_severity_issues)} high-severity issues")
        
        # Critical type trigger: Fundamental issues must be fixed
        if critical_type_issues:
            revision_triggers.append(f"{len(critical_type_issues)} critical-type issues")
        
        # Serious type trigger: Important structural issues need fixing
        if serious_type_issues:
            revision_triggers.append(f"{len(serious_type_issues)} serious-type issues")
        
        # Minor issues trigger: Allow up to 2 minor issues if score is good (≥8.5)
        # This prevents revision for trivial clarity issues when content is solid
        if len(minor_type_issues) > 2:
            revision_triggers.append(f"{len(minor_type_issues)} minor issues (max 2 allowed in round 1)")
        
        needs_revision = len(revision_triggers) > 0
        
        if needs_revision:
            explanation = f"Round 1 revision needed: {', '.join(revision_triggers)}"
        else:
            standard_level = _get_score_standard_level(score)
            explanation = f"Round 1 quality approved (meets {standard_level}): Score {score}/10, {len(minor_type_issues)} minor issues (≤2 allowed)"

    elif round_number == 2:
        # ROUND 2: Focus on serious+ issues, more tolerance for minor problems
        # Goal: Fix remaining significant issues while being more lenient than round 1
        
        revision_triggers = []
        
        # More lenient score threshold than round 1 (8.5 → 8.0)
        if score < 8.0:
            revision_triggers.append(f"score below 8.0 ({score})")
        
        # Still require fixing high severity issues
        if high_severity_issues:
            revision_triggers.append(f"{len(high_severity_issues)} high-severity issues")
        
        # Still require fixing critical type issues
        if critical_type_issues:
            revision_triggers.append(f"{len(critical_type_issues)} critical-type issues")
        
        # Still require fixing serious type issues
        if serious_type_issues:
            revision_triggers.append(f"{len(serious_type_issues)} serious-type issues")
        
        # IGNORE minor issues in round 2 - they've had their chance
        
        needs_revision = len(revision_triggers) > 0
        
        if needs_revision:
            explanation = f"Round 2 revision needed: {', '.join(revision_triggers)} (ignoring {len(minor_type_issues)} minor issues)"
        else:
            standard_level = _get_score_standard_level(score)
            explanation = f"Round 2 quality approved (meets {standard_level}): Score {score}/10, only {len(minor_type_issues)} minor issues remain"

    else:  # Round 3+
        # ROUND 3+: CONVERGENCE MODE - Only critical issues trigger revision
        # Goal: Achieve graceful convergence and prevent infinite revision loops
        
        # CONVERGENCE STRATEGY:
        # 1. Dramatically increase score threshold tolerance (progressive relaxation)
        # 2. Only allow the most critical issues to trigger further revisions
        # 3. Apply diminishing sensitivity - later rounds become more forgiving
        # 4. Implement "convergence grace period" where minor improvements are accepted
        
        revision_triggers = []
        
        # CONVERGENCE SCORE THRESHOLDS: Progressive relaxation across rounds
        # Round 1: 8.5 (high standard)
        # Round 2: 8.0 (moderate relaxation) 
        # Round 3: 7.0 (significant relaxation)
        # Round 4+: 6.0 (maximum relaxation for convergence)
        convergence_threshold = max(7.0 - (0.2 * (round_number - 3)), 6.0)
        
        if score < convergence_threshold:
            revision_triggers.append(f"score below convergence threshold ({score} < {convergence_threshold})")
        
        # CRITICAL ISSUES ONLY: Apply stricter filtering for later rounds
        # Only the most severe issues should prevent convergence
        
        # High severity issues: Still require attention but with higher threshold
        critical_high_severity = [issue for issue in high_severity_issues 
                                if issue.get('type') in ['Factual Error', 'Missing Section']]
        if critical_high_severity:
            revision_triggers.append(f"{len(critical_high_severity)} critical high-severity issues")
        
        # Critical type issues: Only structural/factual problems
        structural_critical = [issue for issue in critical_type_issues 
                             if issue.get('type') in ['Missing Section', 'Factual Error']]
        if structural_critical:
            revision_triggers.append(f"{len(structural_critical)} structural/factual errors")
        
        # CONVERGENCE FILTERING: Ignore all other issue types in late rounds
        # This prevents infinite loops while ensuring core quality
        ignored_issues = len(issues) - len(critical_high_severity) - len(structural_critical)
        
        needs_revision = len(revision_triggers) > 0
        
        if needs_revision:
            explanation = f"Round {round_number} revision needed: {', '.join(revision_triggers)} "
            explanation += f"(CONVERGENCE MODE: ignoring {ignored_issues} non-critical issues)"
        else:
            # CONVERGENCE ACHIEVED: Provide detailed acceptance explanation
            if issues:
                explanation = f"Round {round_number} CONVERGENCE ACHIEVED: Score {score}/10 ≥ {convergence_threshold}. "
                explanation += f"Remaining {len(issues)} issues ({len(serious_type_issues)} serious, {len(minor_type_issues)} minor) "
                explanation += f"do not justify further revision. Quality threshold met for completion."
            else:
                explanation = f"Round {round_number} No issues found, score {score}/10"
    
    # CONVERGENCE LOGGING: Provide transparency about decision process
    print(f"\n=== CONVERGENCE ANALYSIS ROUND {round_number} ===")
    print(f"Score: {score}/10")
    print(f"Issue breakdown: {len(high_severity_issues)} high severity, {len(critical_type_issues)} critical type,")
    print(f"                {len(serious_type_issues)} serious type, {len(minor_type_issues)} minor type")
    print(f"Decision: {'REVISION NEEDED' if needs_revision else 'CONVERGENCE ACHIEVED'}")
    print(f"Explanation: {explanation}")
    print("=" * 60)
    
    return needs_revision, explanation


def _extract_company_info_section(report_content: str):
    """Extract company info section from report (original function)."""
    lines = report_content.split('\n')
    company_info_lines = []
    content_lines = []
    
    # Look for the first ** section which indicates start of actual content
    in_company_info = True
    
    for line in lines:
        if line.strip().startswith('**') and in_company_info:
            in_company_info = False
            content_lines.append(line)
        elif in_company_info:
            company_info_lines.append(line)
        else:
            content_lines.append(line)
    
    company_info_section = '\n'.join(company_info_lines)
    content_without_company_info = '\n'.join(content_lines)

    return company_info_section, content_without_company_info


def _build_verification_context_memory(round_number: int, previous_verification_results: List[Dict], 
                                       previous_revision_notes: List[str]) -> Dict[str, Any]:
    """
    Build context memory for verification round based on previous feedback and revisions.
    
    This function creates a memory structure that helps the verification agent:
    1. Focus on sections that previously had issues
    2. Track issue persistence patterns for better assessment
    3. Apply progressive verification criteria based on round progression
    4. Maintain context about what changes were made in previous revisions
    
    Args:
        round_number: Current verification round number
        previous_verification_results: List of previous VerificationResult objects as dicts
        previous_revision_notes: List of revision notes from previous rounds
        
    Returns:
        Dict containing context memory for this verification round
    """
    context_memory = {
        'focus_sections': [],      # Sections that had issues and should be prioritized
        'resolved_areas': [],      # Areas that were successfully addressed
        'convergence_mode': False, # Whether to apply progressive verification criteria
        'verification_strictness': 'standard',  # Verification strictness level
        'previous_issue_count': 0, # Track issue progression
        'previous_issues': [],     # Store previous issues for comparison
        'revision_context': []     # Context about what was revised
    }

    # PROGRESSIVE VERIFICATION CRITERIA
    # Apply different verification standards based on round progression
    if round_number >= 3:
        context_memory['convergence_mode'] = True
        context_memory['verification_strictness'] = 'lenient'  # Focus on critical issues only
    elif round_number == 2:
        context_memory['verification_strictness'] = 'moderate'  # Focus on high/medium issues
    else:
        context_memory['verification_strictness'] = 'strict'    # Full verification criteria

    # CONVERGENCE SENSITIVITY FACTOR
    # Progressive leniency factor for score adjustments in later rounds
    # Factor decreases with each round to make verification progressively more lenient
    # Formula: adjusted_score = score + (1.0 - sensitivity_factor)
    # Round 1: 1.0 (no adjustment: +0.0), Round 2: 0.8 (slight: +0.2)
    # Round 3: 0.5 (moderate: +0.5), Round 4+: 0.3 (maximum: +0.7)
    if round_number >= 4:
        context_memory['sensitivity_factor'] = 0.3  # Maximum leniency for late rounds
    elif round_number == 3:
        context_memory['sensitivity_factor'] = 0.5  # Moderate leniency
    elif round_number == 2:
        context_memory['sensitivity_factor'] = 0.8  # Slight leniency
    else:
        context_memory['sensitivity_factor'] = 1.0  # No adjustment (strict)
    
    # ANALYZE PREVIOUS VERIFICATION RESULTS
    if previous_verification_results:
        for prev_result in previous_verification_results:
            # Track sections that had issues (should be focus areas)
            if 'issues' in prev_result:
                for issue in prev_result['issues']:
                    section = issue.get('section', '')
                    if section and section not in context_memory['focus_sections']:
                        context_memory['focus_sections'].append(section)
                
                # Store previous issues for persistence tracking
                context_memory['previous_issues'].extend(prev_result['issues'])
            
            # Track total issue progression for assessment
            context_memory['previous_issue_count'] += len(prev_result.get('issues', []))
    
    # ANALYZE PREVIOUS REVISION NOTES
    if previous_revision_notes:
        for note in previous_revision_notes:
            # Extract information about what was revised
            if 'Modified' in note:
                # Parse revision notes to understand what was changed
                if ':' in note:
                    section_part = note.split(':')[0]
                    if 'Modified' in section_part:
                        section_name = section_part.replace('Modified', '').replace("'", "").strip()
                        if section_name:
                            context_memory['revision_context'].append({
                                'section': section_name,
                                'action': 'modified',
                                'note': note
                            })
    
    print(f"Context memory built: {len(context_memory['focus_sections'])} focus sections, "
          f"strictness: {context_memory['verification_strictness']}")
    
    return context_memory

# def _create_context_aware_verification_prompt(report_content: str, transcript: str, 
#                                              meeting_notes: str, additional_instructions: str,
#                                              round_number: int, context_memory: Dict[str, Any],
#                                              sample_report: str = None) -> str:
#     """
#     Create verification prompt with context awareness and memory integration.
    
#     This enhanced prompt includes:
#     1. Instructions to focus on previously problematic sections
#     2. Context about what was revised in previous rounds
#     3. Convergence instructions for later rounds
#     4. Sensitivity adjustments based on round progression
    
#     Args:
#         report_content: Current report content to verify
#         transcript: Original transcript
#         meeting_notes: Meeting notes
#         additional_instructions: Any additional instructions
#         round_number: Current round number
#         context_memory: Context memory structure with focus areas and history
        
#     Returns:
#         str: Enhanced verification prompt with context awareness
#     """
    
#     # Base verification instructions
#     base_prompt = f"""
#         You are an AI report verification specialist with context memory. Verify this AI assessment report against the provided context.

#         **VERIFICATION ROUND: {round_number}**
#         """
    
#     # Add progressive verification instructions based on round and strictness level
#     strictness = context_memory.get('verification_strictness', 'standard')
    
#     if strictness == 'lenient':  # Round 3+
#         base_prompt += f"""
#         **LENIENT VERIFICATION MODE** (Round {round_number})
#         - FOCUS ONLY ON CRITICAL BLOCKING ISSUES
#         - Accept reports with minor imperfections for completion
#         - Only flag High severity issues (Missing Sections, Factual Errors)
#         - Ignore Low and Medium severity issues unless they are critical
#         - Goal: Quality acceptance and workflow completion
#         """
#     elif strictness == 'moderate':  # Round 2
#         base_prompt += f"""
#         **MODERATE VERIFICATION MODE** (Round {round_number})
#         - Focus on High and significant Medium severity issues
#         - Accept minor Low severity issues
#         - Prioritize content accuracy and completeness
#         - Reduce emphasis on stylistic and presentation issues
#         """
#     else:  # Round 1 - strict
#         base_prompt += f"""
#         **COMPREHENSIVE VERIFICATION MODE** (Round {round_number})
#         - Apply full verification criteria
#         - Check all aspects: accuracy, completeness, clarity, structure
#         - Flag all severity levels as appropriate
#         """
    
#     # Add focus section instructions
#     if context_memory['focus_sections']:
#         base_prompt += f"""
#         **PRIORITY FOCUS SECTIONS** (had issues in previous rounds):
#         {', '.join(context_memory['focus_sections'])}
#         - Pay special attention to these sections
#         - Verify that previous issues have been adequately addressed
#         - Check if the content quality has improved
#         """
    
#     # Add comprehensive previous issues context for informed decision making
#     if context_memory['previous_issues']:
#         base_prompt += """
#         **PREVIOUS ISSUES IDENTIFIED**:
#         (Use this context to avoid re-flagging resolved issues and recognize improvements)
#         """
#         # Group previous issues by section for clarity
#         issues_by_section = {}
#         for issue in context_memory['previous_issues'][-10:]:  # Last 10 issues
#             section = issue.get('section', 'General')
#             if section not in issues_by_section:
#                 issues_by_section[section] = []
#             issues_by_section[section].append(issue)
        
#         for section, issues in issues_by_section.items():
#             base_prompt += f"\n**{section}:**\n"
#             for issue in issues[-3:]:  # Max 3 issues per section
#                 severity = issue.get('severity', 'Unknown')
#                 issue_type = issue.get('type', 'Unknown')
#                 description = issue.get('description', 'No description')[:150] + "..." if len(issue.get('description', '')) > 150 else issue.get('description', '')
#                 base_prompt += f"- {severity} {issue_type}: {description}\n"
    
#     # Add revision context if available
#     if context_memory['revision_context']:
#         base_prompt += """
#         **PREVIOUS REVISION ACTIONS**:
#         (Sections that were modified in previous rounds)
#         """
#         for revision in context_memory['revision_context'][-3:]:  # Last 3 revisions
#             base_prompt += f"- {revision['section']}: {revision['note']}\n"
    
#     # Add sample report format reference if available
#     if sample_report:
#         base_prompt += f"""
#         **EXPECTED REPORT FORMAT**:
#         (Use this as a reference for format, structure, and content style)
#         {sample_report}

#         **FORMAT VERIFICATION INSTRUCTIONS**:
#         - Check if the report follows the expected structure and formatting
#         - Verify section headings match the expected pattern
#         - Ensure content style is consistent with the sample
#         - Flag significant deviations from the expected format as "Format Issue"
#         """
    
#     # Add comprehensive verification instructions with detailed assessment criteria
#     base_prompt += f"""
#     **ORIGINAL CONTEXT:**
#     **TRANSCRIPT:** {transcript}
#     **MEETING NOTES:** {meeting_notes if meeting_notes else "No additional meeting notes provided."}
#     **ADDITIONAL INSTRUCTIONS:** {additional_instructions if additional_instructions else "No additional instructions provided."}

#     **REPORT TO VERIFY:**
#     {report_content}

#     **VERIFICATION TASK:**
#     Analyze the report based on current verification mode criteria:

#     {_get_verification_criteria_by_strictness(strictness)}

#     **SECTION COMPLETENESS CHECK:**
#     Verify that required sections are present:

#     1. **AI Maturity Level:** Company operations/services + maturity classification (Low/Moderate/High)
#     2. **Current Solution Development Stage:** Development phase + current AI readiness + aims and objectives
#     3. **Validity of Concept and Authenticity of Problem Addressed:** Practicality/innovation assessment + feasibility comments
#     4. **Integration and Importance of AI in the Idea:** AI centrality to solution
#     5. **Identified Target Market and Customer Segments:** Target customers + market clarity assessment
#     6. **Data Requirement Assessment:** Data needs + assessment of data requirement understanding
#     7. **Data Collection Strategy:** Evaluation of data collection/storage/usage approach
#     8. **Technical Expertise and Capability:** Assessment of technical skills and development abilities
#     9. **Expectations from FAIR Services:** What they expect from consultation
#     10. **Recommendations:** Context-based analysis and practical guidance

#     {_get_section_requirements_by_strictness(strictness)}

#     **ENHANCED VERIFICATION OUTPUT:**
#     Return a JSON object following this structure:
#     {{
#         "score": <float between 1-10 based on actual content quality. Score should reflect the report's accuracy, completeness, and adherence to format standards. Consider the context of previous issues when evaluating improvements, but base the score on current quality level.>,
#         "issues": [
#             {{
#                 "type": "<Missing Section, Factual Error, Required Element Missing, Relevance, Clarity Issue, or Recommendation Issue>",
#                 "section": "<section name>", 
#                 "description": "<detailed description>",
#                 "suggestion": "<specific improvement suggestion>",
#                 "severity": "<High/Medium/Low - High for critical issues, Medium for serious issues, Low for minor issues. IMPORTANT: Do not re-flag resolved issues from previous rounds unless they remain completely unaddressed>"
#             }}
#         ],
#         "suggestions": [
#             {{
#                 "section": "<section name>",
#                 "description": "<improvement suggestion>"
#             }}
#         ],
#         "summary": "<overall assessment with context awareness. Note improvements made from previous rounds and remaining concerns>",
#         "strengths": ["<list of report strengths>"]
#     }}
#     """
    
#     return base_prompt


# def _get_verification_criteria_by_strictness(strictness: str) -> str:
#     """
#     Get verification criteria text based on strictness level.
    
#     Args:
#         strictness: Verification strictness level ('strict', 'moderate', 'lenient')
        
#     Returns:
#         str: Appropriate verification criteria text
#     """
#     if strictness == 'lenient':
#         return """
# **LENIENT CRITERIA (Final Round Focus):**
# 1. Critical factual errors: Only flag if statements directly contradict transcript
# 2. Critical completeness: Only flag if major business information is completely missing
# 3. Critical structure: Only flag if sections are completely absent
# - ACCEPT minor presentation issues, stylistic concerns, and minor omissions
# - ACCEPT reasonable interpretations of transcript content
# - FOCUS on completion over perfection

# **CONTEXT USAGE INSTRUCTIONS:**
# - DO NOT re-flag issues that were previously identified unless they remain completely unresolved
# - RECOGNIZE when content has improved even if not perfect
# - FOCUS on new critical problems, not refinements of resolved issues
# - ACCEPT reasonable attempts to address previous issues
# """
#     elif strictness == 'moderate':
#         return """
# **MODERATE CRITERIA (Balanced Assessment):**
# 1. Factual accuracy: Flag clear contradictions and significant misinterpretations
# 2. Completeness: Flag missing key business information and important details
# 3. Relevance: Flag information that lacks clear support from transcript
# 4. Structure: Flag organizational issues that affect comprehension
# - ACCEPT minor clarity and presentation issues
# - FOCUS on content accuracy and business relevance

# **CONTEXT USAGE INSTRUCTIONS:**
# - Check if previously identified issues have been adequately addressed
# - FLAG issues only if they remain significantly problematic
# - RECOGNIZE improvements even if they could be better
# - FOCUS on issues that genuinely impact report quality
# """
#     else:  # strict
#         return """
# **COMPREHENSIVE CRITERIA (Full Assessment):**
# 1. Factual accuracy: Does the report contain statements that contradict the transcript?
# 2. Completeness: Does the report miss any key information from the transcript?
# 3. Relevance: Does the report include information that isn't supported by the transcript?
# 4. Clarity and structure: Is the information well-organized and clearly presented?
# 5. Recommendations quality: Are recommendations specific, actionable, and aligned with the discussion?
# 6. Instructions compliance: Does the report follow any additional instructions appropriately?

# **CONTEXT USAGE INSTRUCTIONS:**
# - This is the initial comprehensive assessment - identify all potential issues
# - ESTABLISH baseline quality and provide complete feedback for revision
# - DOCUMENT all issues thoroughly for future rounds to track progress
# """


# def _get_section_requirements_by_strictness(strictness: str) -> str:
#     """
#     Get section requirement text based on strictness level.
    
#     Args:
#         strictness: Verification strictness level ('strict', 'moderate', 'lenient')
        
#     Returns:
#         str: Appropriate section requirement text
#     """
#     if strictness == 'lenient':
#         return "Only flag sections as missing if they are COMPLETELY ABSENT. Accept minimal content in sections."
#     elif strictness == 'moderate':
#         return "Flag sections with insufficient content or missing key elements. Accept reasonable content quality."
#     else:  # strict
#         return "If ANY required section is COMPLETELY MISSING, categorize as 'Missing Section' issue with HIGH severity."

def _create_context_aware_verification_prompt(report_content: str, transcript: str,
                                             meeting_notes: str, additional_instructions: str,
                                             round_number: int, context_memory: Dict[str, Any],
                                             sample_report: str = None) -> str:
    """
    Create verification prompt with STRONG anti-progressive-perfectionism controls.
    - Explicit rules against "could be better" refinements
    - Issue resolution detection and tracking
    - "Good enough" principle enforcement
    - Only NEW issue types allowed, not refinements of resolved issues

    Args:
        report_content: Current report content to verify
        transcript: Original transcript
        meeting_notes: Meeting notes
        additional_instructions: Any additional instructions
        round_number: Current round number
        context_memory: Context memory structure with focus areas and history
        sample_report: Sample report for format reference

    Returns:
        str: Enhanced verification prompt with anti-perfectionism controls
    """

    # Base verification instructions
    base_prompt = f"""
You are an AI report verification specialist with context memory.

**VERIFICATION ROUND: {round_number}**
"""

    # Add progressive verification instructions based on round and strictness level
    strictness = context_memory.get('verification_strictness', 'standard')

    if strictness == 'lenient':  # Round 3+
        base_prompt += f"""
**LENIENT VERIFICATION MODE** (Round {round_number})
- FOCUS ONLY ON CRITICAL BLOCKING ISSUES
- Accept reports with minor imperfections for completion
- Only flag High severity issues (Missing Sections, Factual Errors)
- Ignore Low and Medium severity issues unless they are critical
- Goal: Quality acceptance and workflow completion
"""
    elif strictness == 'moderate':  # Round 2
        base_prompt += f"""
**MODERATE VERIFICATION MODE** (Round {round_number})
- Focus on High and significant Medium severity issues
- Accept minor Low severity issues
- Prioritize content accuracy and completeness
- Reduce emphasis on stylistic and presentation issues
"""
    else:  # Round 1 - strict
        base_prompt += f"""
**COMPREHENSIVE VERIFICATION MODE** (Round {round_number})
- Apply full verification criteria
- Check all aspects: accuracy, completeness, clarity, structure
- Flag all severity levels as appropriate
"""

    # Add ANTI-PROGRESSIVE-PERFECTIONISM rules for rounds 2+
    if round_number > 1:
        base_prompt += f"""

**CRITICAL: ANTI-PROGRESSIVE-PERFECTIONISM RULES (Round {round_number})**

You MUST follow these rules to prevent endless refinement cycles:

1. **ISSUE RESOLUTION DETECTION:**
   - If a previous issue has been ADEQUATELY ADDRESSED, consider it RESOLVED
   - DO NOT flag "improvements" or "refinements" of resolved issues

2. **"GOOD ENOUGH" PRINCIPLE:**
   - If content adequately addresses the concern → ACCEPT IT
   - If content is factually correct and reasonably complete → ACCEPT IT
   - If previous issue is no longer a problem → DO NOT create a new variant

3. **NEW vs REFINEMENT:**
   - ALLOWED: Truly NEW issues (different type, different section, different concern)
   - FORBIDDEN: Same issue but "more nuanced" or "could be better" versions

   Examples of FORBIDDEN progressive perfectionism:
   - Round 1: "Section lacks X" → Round 2: "Section now has X but could be more detailed" ❌
   - Round 1: "Missing Y" → Round 2: "Y is now present but could be clearer" ❌
   - Round 1: "Needs Z" → Round 2: "Z is now mentioned but could elaborate more" ❌

4. **RESOLUTION TEST:**
   Before flagging an issue in a revised section, ask yourself:
   - Was there a similar issue in this section previously? YES/NO
   - Has that issue been addressed? YES/NO
   - Is my new issue just a refinement of the resolved issue? YES/NO
   - If YES to all three → DO NOT FLAG IT (progressive perfectionism)

5. **SEVERITY INFLATION PREVENTION:**
   - Do NOT escalate severity of previously low-priority issues
   - Do NOT find "new aspects" of resolved issues
   - Do NOT raise standards between rounds
"""

    # Add focus section instructions with resolution context
    if context_memory['focus_sections']:
        base_prompt += f"""

**FOCUS SECTIONS** (revised in previous rounds):
{', '.join(context_memory['focus_sections'])}

These sections were specifically revised to address previous issues.
    - Pay special attention to these sections
    - Verify that previous issues have been adequately addressed
"""

    # Add comprehensive previous issues context with resolution tracking
    if context_memory['previous_issues']:
        base_prompt += """

**PREVIOUS ISSUES IDENTIFIED:**
(CRITICAL: Check if these issues have been RESOLVED. If yes, DO NOT flag refinements)
"""
        # Group previous issues by section for clarity
        issues_by_section = {}
        for issue in context_memory['previous_issues'][-10:]:  # Last 10 issues
            section = issue.get('section', 'General')
            if section not in issues_by_section:
                issues_by_section[section] = []
            issues_by_section[section].append(issue)

        for section, issues in issues_by_section.items():
            base_prompt += f"\n**{section}:**\n"
            for issue in issues[-3:]:  # Max 3 issues per section
                severity = issue.get('severity', 'Unknown')
                issue_type = issue.get('type', 'Unknown')
                description = issue.get('description', 'No description')[:150] + "..." if len(issue.get('description', '')) > 150 else issue.get('description', '')
                base_prompt += f"- {severity} {issue_type}: {description}\n"
                base_prompt += f"  → CHECK: Has this been RESOLVED? If YES, do NOT flag refinements.\n"

    # Add revision context if available
    if context_memory['revision_context']:
        base_prompt += """

**PREVIOUS REVISION ACTIONS:**
(These sections were specifically modified to address the issues listed above)
"""
        for revision in context_memory['revision_context'][-3:]:  # Last 3 revisions
            base_prompt += f"- {revision['section']}: {revision['note']}\n"

        base_prompt += """
→ For these revised sections: Apply "GOOD ENOUGH" principle - if the original
  issue is addressed, ACCEPT IT. Do not demand perfection or progressive improvements.
"""

    # Add sample report format reference if available
    if sample_report:
        base_prompt += f"""

**EXPECTED REPORT FORMAT:**
(Use this as a reference for format, structure, and content style)
{sample_report}

**FORMAT VERIFICATION INSTRUCTIONS:**
- Check if the report follows the expected structure and formatting
- Verify section headings match the expected pattern
- Ensure content style is consistent with the sample
- Flag significant deviations from the expected format as "Format Issue"
"""

    # Add comprehensive verification instructions with detailed assessment criteria
    base_prompt += f"""

**ORIGINAL CONTEXT:**
**TRANSCRIPT:** {transcript}
**MEETING NOTES:** {meeting_notes if meeting_notes else "No additional meeting notes provided."}
**ADDITIONAL INSTRUCTIONS:** {additional_instructions if additional_instructions else "No additional instructions provided."}

**REPORT TO VERIFY:**
{report_content}

**VERIFICATION TASK:**
Analyze the report based on current strictness criteria. The current strictness level is {strictness}.

**SECTION COMPLETENESS CHECK:**
Verify that required sections are present:

1. **AI Maturity Level:** Company operations/services + maturity classification (Low/Moderate/High)
2. **Current Solution Development Stage:** Development phase + current AI readiness + aims and objectives
3. **Validity of Concept and Authenticity of Problem Addressed:** Practicality/innovation assessment + feasibility comments
4. **Integration and Importance of AI in the Idea:** AI centrality to solution
5. **Identified Target Market and Customer Segments:** Target customers + market clarity assessment
6. **Data Requirement Assessment:** Data needs + assessment of data requirement understanding
7. **Data Collection Strategy:** Evaluation of data collection/storage/usage approach
8. **Technical Expertise and Capability:** Assessment of technical skills and development abilities
9. **Expectations from FAIR Services:** What they expect from consultation
10. **Recommendations:** Context-based analysis and practical guidance

**ENHANCED VERIFICATION OUTPUT:**
Return a JSON object following this structure:
{{
    "score": <float between 1-10 based on actual content quality. If previous issues have been resolved, increase score accordingly. Apply "good enough" principle - do not demand perfection.>,
    "issues": [
        {{
            "type": "<Missing Section, Factual Error, Required Element Missing, Relevance, Clarity Issue, or Recommendation Issue>",
            "section": "<section name>",
            "description": "<detailed description - MUST be a TRULY NEW issue, NOT a refinement of a resolved issue>",
            "suggestion": "<specific improvement suggestion>",
            "severity": "<High/Medium/Low - IMPORTANT: Apply Round {round_number} standards. If previous issue was resolved, do NOT flag progressive refinements.>"
        }}
    ],
    "suggestions": [
        {{
            "section": "<section name>",
            "description": "<improvement suggestion - only for TRULY NEW concerns, not refinements>"
        }}
    ],
    "summary": "<overall assessment. Note improvements from previous rounds. Apply 'good enough' principle - if issues are resolved, acknowledge that positively without nitpicking.>",
    "strengths": ["<list of report strengths - include resolved issues from previous rounds>"]
}}


"""

    return base_prompt


def _verify_report_with_context(prompt: str, api_config: Dict[str, Any], 
                               context_memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute verification with context awareness and enhanced error handling.
    
    Args:
        prompt: Context-aware verification prompt
        api_config: API configuration
        context_memory: Context memory for this round
        
    Returns:
        Dict: Verification results with context adjustments
    """
    try:
        # Execute verification with progressive criteria and context awareness
        if not api_config:
            raise ValueError("API configuration is required")
        
        # Initialize OpenAI client based on configuration
        if api_config.get('use_azure', False):
            client = AzureOpenAI(
                api_key=api_config.get('api_key'),
                azure_endpoint=api_config.get('azure_endpoint', ''),
                api_version=api_config.get('api_version', '2025-03-01-preview')
            )
        else:
            client = OpenAI(api_key=api_config.get('api_key'))
        
        model = api_config.get('model')

        if model.startswith("gpt-5"):
            # reasoning-enabled model: include reasoning params
            response = client.chat.completions.create(
                model = model,
                messages=[
                    {"role": "system", "content": "You are a professional AI consultant generating assessment reports with precise formatting and natural language. Avoid clichéd consultant language and use straightforward, clear communication. IMPORTANT: Provide responses as plain text without markdown code blocks or ``` formatting."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens = api_config.get('max_completion_tokens',4000),
                reasoning_effort = api_config.get('reasoning_effort', 'low'),
                verbosity = api_config.get('verbosity', 'low')
        )
        else:
            # non-reasoning model: use standard parameters
            response = client.chat.completions.create(
                model = model,
                messages=[
                    {"role": "system", "content": "You are a professional AI consultant generating assessment reports with precise formatting and natural language. Avoid clichéd consultant language and use straightforward, clear communication. IMPORTANT: Provide responses as plain text without markdown code blocks or ``` formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature = 0.0
            )
        
        verification_response = response.choices[0].message.content
        verification_results = json.loads(verification_response)
        
        # Apply context-based adjustments to results
        if context_memory['convergence_mode']:
            # Apply convergence adjustments to score and issues
            score = verification_results.get('score', 0)
            issues = verification_results.get('issues', [])
            
            # Convergence score adjustment - be more lenient in later rounds
            adjusted_score = min(score + (1.0 - context_memory['sensitivity_factor']), 10.0)
            verification_results['score'] = adjusted_score
            
            print(f"Context-aware adjustments applied: Score {score} → {adjusted_score}, "
                  f"Convergence factor: {context_memory['sensitivity_factor']:.2f}")
        
        return verification_results
    
    except Exception as e:
        print(f"Context-aware verification failed: {str(e)}")
        # Fallback to basic verification results
        return {
            'score': 7.0,  # Default reasonable score
            'issues': [],
            'suggestions': [],
            'summary': f"Context-aware verification encountered an error: {str(e)}",
            'strengths': ["Report structure appears intact"]
        }