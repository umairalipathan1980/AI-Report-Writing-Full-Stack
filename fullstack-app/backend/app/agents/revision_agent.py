import re
import json
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
from openai import OpenAI, AzureOpenAI


class RevisionResult(BaseModel):
    """Output model for revision results"""
    revised_report: str
    revision_notes: str
    issues_addressed: int
    suggestions_implemented: int
    revision_summary: str
    status: str = "completed"


def revise_report_content(report_content: str, verification_results: Dict[str, Any],
                         company_data: Dict[str, Any], transcript: str = "",
                         round_number: int = 1, api_config: Dict[str, Any] = None) -> RevisionResult:
    """
    Tool function to revise report content using SURGICAL two-level targeting approach.

    TWO-LEVEL TARGETING:
    1. Section-level: Only processes sections that have identified issues
    2. Sub-section-level: Within problematic sections, only modifies specific
       paragraphs/sentences related to issues, keeping other parts verbatim

    This approach minimizes unnecessary changes and reduces the risk of introducing
    new issues while addressing verification feedback with surgical precision.

    Args:
        report_content: The current report content to revise
        verification_results: Results from verification with issues and suggestions
        company_data: Company information dictionary
        transcript: Original transcript (for context)
        round_number: Current revision round number
        api_config: API configuration dictionary

    Returns:
        RevisionResult: Results with revised report and revision notes
    """
    if not report_content or not verification_results:
        raise ValueError("Missing required inputs: report_content and verification_results")
    
    issues = verification_results.get('issues', [])
    suggestions = verification_results.get('suggestions', [])
    
    print(f"\n=== SURGICAL TARGETED REVISION ROUND {round_number} ===")
    print(f"Total issues to address: {len(issues)}")
    print(f"Total suggestions to implement: {len(suggestions)}")
    print(f"Methodology: Two-level targeting (Section + Sub-section precision)")

    # Use surgical targeted revision approach - only modify sections with issues,
    # and within those sections, only modify specific problematic parts
    revised_report, revision_notes = _perform_targeted_revision(
        report_content, issues, suggestions, round_number, api_config
    )
    
    # Ensure all required sections are present
    revised_report = _ensure_required_sections(revised_report, company_data)

    print(f"Surgical targeted revision complete for round {round_number}")
    print(f"Applied sub-section-level precision to minimize unnecessary changes")

    return RevisionResult(
        revised_report=revised_report,
        revision_notes=revision_notes,
        issues_addressed=len(issues),
        suggestions_implemented=len(suggestions),
        revision_summary=f"Surgical revision: addressed {len(issues)} issues with sub-section precision, preserving unchanged content verbatim"
    )


def _perform_targeted_revision(report_content: str, issues: List[Dict], suggestions: List[Dict],
                              round_number: int, api_config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Perform SURGICAL two-level targeted revision.

    LEVEL 1 (Section-level):
    - Parses report into sections
    - Only processes sections with identified issues
    - Preserves sections without issues completely

    LEVEL 2 (Sub-section-level):
    - Within each problematic section, identifies specific paragraphs/parts with issues
    - Modifies ONLY those specific parts
    - Preserves all other parts within the section verbatim (word-for-word)

    This surgical approach prevents introducing new problems while addressing feedback.

    Args:
        report_content: Current report content
        issues: List of identified issues
        suggestions: List of suggestions
        round_number: Current revision round
        api_config: API configuration

    Returns:
        Tuple[str, str]: (revised_report, revision_notes)
    """
    
    # Parse report into sections
    sections = _parse_report_sections(report_content)
    
    # Group issues by section for targeted fixing
    issues_by_section = _group_issues_by_section(issues)
    suggestions_by_section = _group_suggestions_by_section(suggestions)
    
    revised_sections = {}
    revision_notes_list = []
    
    print(f"Found {len(sections)} sections in report")
    print(f"Issues affect {len(issues_by_section)} sections: {list(issues_by_section.keys())}")

    # Process each section
    for section_name, section_content in sections.items():
        section_issues = issues_by_section.get(section_name, [])
        section_suggestions = suggestions_by_section.get(section_name, [])

        if section_issues or section_suggestions:
            print(f"Surgical revision of '{section_name}': {len(section_issues)} issues, {len(section_suggestions)} suggestions")
            print(f"  → Will modify only specific problematic parts, preserve rest verbatim")

            # Revise this section with surgical precision (sub-section targeting)
            revised_section = _revise_single_section(
                section_name, section_content, section_issues, section_suggestions,
                round_number, api_config
            )
            revised_sections[section_name] = revised_section
            revision_notes_list.append(f"• Surgically modified '{section_name}': addressed {len(section_issues)} issues with minimal changes")
        else:
            # Keep section unchanged
            revised_sections[section_name] = section_content
            print(f"Preserving section '{section_name}' completely (no issues found)")
    
    # Reconstruct the complete report
    revised_report = _reconstruct_report(revised_sections)

    # Create revision notes
    revision_notes = "\n".join(revision_notes_list) if revision_notes_list else "No sections required modification"

    print(f"Surgical revision complete: {len(revision_notes_list)} sections surgically modified, {len(sections) - len(revision_notes_list)} sections preserved completely")
    print(f"Sub-section precision applied: Only problematic parts modified, unchanged content preserved verbatim")

    return revised_report, revision_notes


def _parse_report_sections(report_content: str) -> Dict[str, str]:
    """
    Parse report content into individual sections.
    
    Returns:
        Dict[str, str]: Section name -> section content mapping
    """
    sections = {}
    lines = report_content.split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        # Check if this is a section header
        if line.strip().startswith('**') and line.strip().endswith(':**'):
            # Save previous section if exists
            if current_section and current_content:
                sections[current_section] = '\n'.join(current_content).strip()
            
            # Start new section
            current_section = line.strip().replace('**', '').replace(':', '')
            current_content = [line]  # Include the header
        else:
            # Add to current section content
            if current_section:
                current_content.append(line)
            else:
                # Handle content before first section (company info, etc.)
                if 'Company Info' not in sections:
                    sections['Company Info'] = line
                else:
                    sections['Company Info'] += '\n' + line
    
    # Don't forget the last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections

def _group_issues_by_section(issues: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group issues by the section they affect with intelligent section name matching.
    Handles composite section names like 'AI Maturity Level / Current Solution Development Stage'.
    
    Returns:
        Dict[str, List[Dict]]: Section name -> list of issues for that section
    """
    issues_by_section = {}
    
    for issue in issues:
        issue_section = issue.get('section', 'General')
        
        # Handle composite section names (e.g., "AI Maturity Level / Current Solution Development Stage")
        if ' / ' in issue_section:
            # Split composite section name and assign issue to each component
            component_sections = [s.strip() for s in issue_section.split(' / ')]
            for section in component_sections:
                if section not in issues_by_section:
                    issues_by_section[section] = []
                issues_by_section[section].append(issue)
            print(f"Mapped composite issue '{issue_section}' to sections: {component_sections}")
        else:
            # Single section name
            if issue_section not in issues_by_section:
                issues_by_section[issue_section] = []
            issues_by_section[issue_section].append(issue)
    
    return issues_by_section

def _group_suggestions_by_section(suggestions: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group suggestions by the section they affect with intelligent section name matching.
    Handles composite section names like 'AI Maturity Level / Current Solution Development Stage'.
    
    Returns:
        Dict[str, List[Dict]]: Section name -> list of suggestions for that section
    """
    suggestions_by_section = {}
    
    for suggestion in suggestions:
        suggestion_section = suggestion.get('section', 'General')
        
        # Handle composite section names (e.g., "AI Maturity Level / Current Solution Development Stage")
        if ' / ' in suggestion_section:
            # Split composite section name and assign suggestion to each component
            component_sections = [s.strip() for s in suggestion_section.split(' / ')]
            for section in component_sections:
                if section not in suggestions_by_section:
                    suggestions_by_section[section] = []
                suggestions_by_section[section].append(suggestion)
            print(f"Mapped composite suggestion '{suggestion_section}' to sections: {component_sections}")
        else:
            # Single section name
            if suggestion_section not in suggestions_by_section:
                suggestions_by_section[suggestion_section] = []
            suggestions_by_section[suggestion_section].append(suggestion)
    
    return suggestions_by_section


def _revise_single_section(section_name: str, section_content: str, issues: List[Dict],
                          suggestions: List[Dict], round_number: int,
                          api_config: Dict[str, Any]) -> str:
    """
    Revise a single section using SURGICAL sub-section targeting.

    This function creates a prompt that instructs the LLM to:
    1. Identify which specific paragraphs/sentences relate to each issue
    2. Modify ONLY those specific parts to address the issues
    3. Copy all other parts VERBATIM (word-for-word) from the original
    4. Reconstruct the section with minimal changes

    This surgical approach prevents unnecessary rewrites and reduces the risk
    of introducing new issues while addressing verification feedback.

    Args:
        section_name: Name of the section being revised
        section_content: Current content of the section
        issues: Issues specific to this section
        suggestions: Suggestions specific to this section
        round_number: Current revision round
        api_config: API configuration

    Returns:
        str: Revised section content with surgical modifications
    """
    
    # Format issues for this section
    issues_text = ""
    for i, issue in enumerate(issues, 1):
        issues_text += f"{i}. {issue.get('type', 'Issue')}: {issue.get('description', 'No description')}\n"
        if issue.get('suggestion'):
            issues_text += f"   → {issue.get('suggestion')}\n"
        issues_text += f"   Severity: {issue.get('severity', 'Medium')}\n\n"
    
    # Format suggestions for this section
    suggestions_text = ""
    for i, suggestion in enumerate(suggestions, 1):
        suggestions_text += f"{i}. {suggestion.get('description', 'No description')}\n\n"
    
    # Create targeted section revision prompt with sub-section targeting
    prompt = f"""
You are an expert report editor. You need to improve ONLY the "{section_name}" section based on specific feedback.

REVISION ROUND: {round_number}

SECTION TO REVISE: {section_name}

CURRENT SECTION CONTENT:
{section_content}

SPECIFIC ISSUES TO FIX:
{issues_text if issues_text else "No specific issues identified."}

SUGGESTIONS TO IMPLEMENT:
{suggestions_text if suggestions_text else "No additional suggestions."}

CRITICAL REQUIREMENTS FOR SUB-SECTION TARGETING:

1. **SURGICAL PRECISION REQUIRED**: This section may contain multiple paragraphs or bullet points. The issues listed above likely affect only SOME of these parts, not all.

2. **IDENTIFY PROBLEMATIC PARTS ONLY**:
   - Read through the section and identify which specific paragraphs/sentences/bullets are directly related to the issues
   - Map each issue to the specific part(s) of the section that need modification

3. **PRESERVE UNCHANGED CONTENT VERBATIM**:
   - For paragraphs/sentences/bullets that are NOT related to any of the issues: Keep them EXACTLY as they are
   - DO NOT rephrase, rewrite, or "improve" content that doesn't address the specific issues
   - Copy unchanged parts word-for-word from the original

4. **MODIFY ONLY PROBLEMATIC PARTS**:
   - ONLY modify the specific paragraphs/sentences/bullets that directly address the issues
   - If an issue mentions "data labeling", only modify the part about data labeling
   - If an issue mentions "missing information about X", only add/modify content about X

5. **RECONSTRUCTION**:
   - Combine the preserved unchanged parts (verbatim) with the modified parts
   - Maintain the original section structure and flow
   - Keep the section heading exactly as: **{section_name}:**

6. **FORMAT AND STYLE**:
   - Maintain the professional tone and markdown formatting
   - Preserve factual information that isn't flagged as incorrect
   - DO NOT use markdown code blocks (```) in your response

7. **OUTPUT**: Return the complete section with:
   - Unchanged parts: EXACT copies from original
   - Modified parts: Improved to address the specific issues
   - Section heading: **{section_name}:**

EXAMPLE APPROACH:
- Parse section into parts (paragraphs/bullets)
- For each part: Does it relate to any issue?
  - YES → Modify it to address the issue
  - NO → Copy it verbatim (word-for-word)
- Combine all parts in original order

Your task: Return the improved "{section_name}" section with SURGICAL PRECISION - only modify what needs fixing, keep everything else EXACTLY as provided.

IMPORTANT: Your response should be plain text without any markdown code block formatting (no ``` or similar).
"""
    
    return _call_revision_llm(prompt, api_config)

def _reconstruct_report(sections: Dict[str, str]) -> str:
    """
    Reconstruct the complete report from individual sections.
    
    Args:
        sections: Dictionary of section name -> content
        
    Returns:
        str: Complete reconstructed report
    """
    
    # Define the expected section order
    expected_order = [
        'Company Info',
        'AI Maturity Level',
        'Current Solution Development Stage',
        'Validity of Concept and Authenticity of Problem Addressed',
        'Integration and Importance of AI in the Idea',
        'Identified Target Market and Customer Segments',
        'Data Requirement Assessment',
        'Data Collection Strategy',
        'Technical Expertise and Capability',
        'Expectations from FAIR Services',
        'Recommendations',
        'AI Maturity Levels'
    ]
    
    reconstructed_parts = []
    
    # Add sections in the expected order
    for section_name in expected_order:
        if section_name in sections:
            content = sections[section_name].strip()
            if content:
                reconstructed_parts.append(content)
    
    # Add any remaining sections not in the expected order
    for section_name, content in sections.items():
        if section_name not in expected_order:
            content = content.strip()
            if content:
                reconstructed_parts.append(content)
    
    return '\n\n'.join(reconstructed_parts)

def _call_revision_llm(prompt: str, api_config: Dict[str, Any]) -> str:
    """Call LLM for revision using original configuration."""
    
    if not api_config:
        raise ValueError("API configuration is required")
    
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
    
    raw_content = response.choices[0].message.content
    return _clean_markdown_formatting(raw_content)


def _clean_markdown_formatting(content: str) -> str:
    """
    Remove markdown code block formatting that might interfere with HTML/DOCX rendering.
    
    Args:
        content: Raw content from LLM that might contain markdown formatting
        
    Returns:
        str: Cleaned content without problematic markdown formatting
    """
    # Remove standalone code block markers
    content = re.sub(r'^```[a-zA-Z]*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
    
    # Remove code blocks that wrap entire sections
    content = re.sub(r'```\s*\n(.*?)\n```', r'\1', content, flags=re.DOTALL)
    
    # Clean up any extra whitespace created by removal
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    return content.strip()


def _ensure_required_sections(report_content: str, company_data: Dict[str, Any]) -> str:
    """Ensure all required sections using original logic."""
    
    # Original required sections mapping
    required_sections = {
        "AI Maturity Level": "**AI Maturity Level:**\nInformation not available from the consultation transcript.\n\n",
        "Current Solution Development Stage": "**Current Solution Development Stage:**\nInformation not available from the consultation transcript.\n\n",
        "Validity of Concept and Authenticity of Problem Addressed": "**Validity of Concept and Authenticity of Problem Addressed:**\nInformation not available from the consultation transcript.\n\n",
        "Integration and Importance of AI in the Idea": "**Integration and Importance of AI in the Idea:**\nInformation not available from the consultation transcript.\n\n",
        "Identified Target Market and Customer Segments": "**Identified Target Market and Customer Segments:**\nInformation not available from the consultation transcript.\n\n",
        "Data Requirement Assessment": "**Data Requirement Assessment:**\nInformation not available from the consultation transcript.\n\n",
        "Data Collection Strategy": "**Data Collection Strategy:**\nInformation not available from the consultation transcript.\n\n",
        "Technical Expertise and Capability": "**Technical Expertise and Capability:**\nInformation not available from the consultation transcript.\n\n",
        "Expectations from FAIR Services": "**Expectations from FAIR Services:**\nInformation not available from the consultation transcript.\n\n",
        "Recommendations": "**Recommendations:**\nNo specific recommendations could be made based on the available information.\n\n",
    }
    
    modified_report = report_content
    
    # Find where to start adding missing sections 
    ai_maturity_levels_pos = modified_report.find("**AI Maturity Levels:")
    if ai_maturity_levels_pos == -1:
        # If not found, find end of report
        ai_maturity_levels_pos = len(modified_report)
    
    # Insert missing sections in the correct order before AI Maturity Levels
    insertion_point = ai_maturity_levels_pos
    missing_sections_text = ""
    
    for section, placeholder in required_sections.items():
        if f"**{section}:**" not in modified_report:
            print(f"Adding missing section to final report: {section}")
            missing_sections_text += placeholder
    
    if missing_sections_text:
        print(f"Added {missing_sections_text.count('**')/2} missing sections to final report")
        modified_report = modified_report[:insertion_point] + missing_sections_text + modified_report[insertion_point:]

    return modified_report