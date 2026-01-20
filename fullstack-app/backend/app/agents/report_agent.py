import os
import re
from typing import Dict, Any
from pydantic import BaseModel
from openai import OpenAI, AzureOpenAI


class ReportResult(BaseModel):
    """Output model for report generation results"""
    report_content: str
    company_data: Dict[str, Any]
    report_summary: str
    status: str = "completed"

def get_sample_report() -> str:
    """
    Get the exact sample report template used for report generation.
    
    Returns:
        str: Sample report template
    """
    return """
        **AI Maturity Level:**
        TechNova Oy is an established company that provides survey creation, distribution, and reporting tools for organizations and researchers. The platform supports both qualitative and quantitative data collection and analysis, with a focus on user experience and flexibility. The company has implemented production AI features, including Azure-based text analytics for sentiment analysis, summaries, and topic extraction. There is ongoing product development, including monthly releases and UI improvements. TechNova Oy has internal programming and AI expertise and has developed proof-of-concept solutions for AI integration. The company is actively experimenting with LLMs and has a knowledge base connected to its assistant. While full operationalization of AI into all core workflows is still in progress and some features remain in development, the presence of production AI capabilities and ongoing integration efforts align with a Moderate AI maturity level. 

        **Current Solution Development Stage:**
        TechNova Oy is in the prototyping and early implementation phase for AI features. The main objectives are to integrate AI into survey creation and reporting. The company has a working proof-of-concept for AI-generated surveys and uses Azure AI for text analytics. However, full integration of AI into the user interface and automation of survey creation are still under development. The reporting module is being enhanced to support more advanced AI-driven analysis of quantitative data. TechNova Oy aims to reduce manual work, improve user onboarding, and provide actionable insights through AI. The company is seeking practical solutions for connecting AI outputs directly to survey creation and for automating data analysis tasks.

        **Validity of Concept and Authenticity of Problem Addressed:**
        The proposed AI concepts address genuine user needs in survey creation and data analysis. Customers have requested AI features to simplify survey design and to gain deeper insights from survey results. The integration of AI into these workflows is practical and aligns with current trends in survey platforms. The scope is clear, focusing on automating repetitive tasks and improving usability. The feasibility is supported by existing technical resources and preliminary experiments, though further development is needed for seamless integration.

        **Integration and Importance of AI in the Idea:**
        AI is central to the planned improvements in both survey creation and reporting. It is intended to automate the generation of survey questions, provide recommendations, and analyze both qualitative and quantitative data. AI will act as an assistant to guide users, reduce manual effort, and enhance the overall functionality of the platform. 

        **Identified Target Market and Customer Segments:**
        TechNova Oy targets organizations, researchers, and thesis writers who require flexible survey tools and advanced reporting capabilities. The market is clearly defined, with a focus on users who benefit from automated survey creation and data analysis. The relevance of the target segments is confirmed by direct customer requests and feedback.

        **Data Requirement Assessment:**
        The company requires structured data in the form of survey templates to be suggested to the users through AI. TechNova Oy has a general understanding of its data needs, supported by an existing knowledge base and survey library. However, there is a need for greater clarity regarding the specific requirements, particularly in the context of AI integration. The process for integrating survey templates into the AI context must be clearly defined to ensure these sources are effectively utilized. 

        **Data Collection Strategy:**
        TechNova Oy collects data through its survey platform, allowing users to create and distribute surveys and gather responses. The system supports exporting data to formats like Excel. There is an established process for storing survey templates and user-generated questions. Currently, these data collection processes are designed primarily to support survey operations and reporting, rather than for AI training or context enrichment. As such, there is no structured plan in place for collecting data specifically to support new AI-driven features. This represents an area that requires further development, and it is recommended that a dedicated data collection strategy be established to ensure the effective implementation of AI capabilities. 

        **Technical Expertise and Capability:**
        TechNova Oy has internal expertise in programming and foundational AI concepts. The CTO has developed proof-of-concept solutions for AI integration, and the team is familiar with LLMs and API-based workflows. However, the team’s experience with advanced AI integration and context engineering is still developing, and current capabilities are primarily at the POC and early implementation stage. The company’s internal expertise does not yet extend to advanced user interface design, robust context management, or seamless integration of AI outputs with core systems. As a result, while TechNova Oy is capable of implementing new AI features at a basic level, achieving full AI productization and advanced integration may require upskilling and/or external support.

        **Expectations from FAIR Services:**
        TechNova Oy expects practical guidance on integrating AI into its survey creation and reporting modules. The company seeks recommendations for integrating AI-generated outputs into the user interface, automating data analysis, and enhancing legacy code management. Support in selecting appropriate AI models, structuring API calls, and validating outputs is also anticipated.

        **Recommendations:**
        - TechNova Oy is advised to prioritize the integration of AI-driven survey creation within the existing user interface. The recommended approach is to use a retrieval-augmented generation (RAG) system to provide relevant context from the knowledge base, including customer documents and historical surveys, to a large language model (LLM). The LLM should generate survey questions in a structured format, such as JSON, which can be directly parsed and imported into the survey editor. This will eliminate manual copy-paste steps and streamline the workflow for users.

        - The company should explore advanced LLMs such as OpenAI’s GPT-5 and Anthropic’s Claude-Sonnet-4 or Claude-Opus-4.1 for both survey generation and code creation tasks. These models can be prompted to produce structured outputs and simple API call code.

        - Connecting the AI assistant to the existing REST API system is a practical next step. By enabling the LLM to make API calls based on user prompts, survey creation and editing can be automated. Setting up an MCP (Model Context Protocol) service that understands the API endpoints will allow the LLM to perform actions such as creating, modifying, and managing surveys directly from the chat interface.

        - For reporting and data analysis, TechNova Oy should identify the most common and recurring analysis questions from users, such as demographic breakdowns and response distributions. A library of analysis code snippets should be developed for these tasks. This allows some flexibility, determinism and cost-efficiency and guards against LLM errors compared to a situation where LLM would create analyses from scratch. The LLM can select and execute the appropriate code based on user queries, ensuring consistent and reliable results. For less frequent or unpredictable questions, direct LLM-based analysis can be used, with mechanisms of validation to minimize errors and hallucinations.

        - The company should continue to use Microsoft Azure AI services for text analytics but expand capabilities to include more nuanced sentiment analysis, entity recognition, and quantitative data summaries. Testing LLMs with a wide range of user questions and data types is recommended to assess accuracy and consistency before full deployment.

        - To improve onboarding and support for new users, consider adding AI-powered suggestions for survey types, consent questions, and best practices directly within the survey creation flow. This will lower the threshold for first-time users and help address common challenges, such as GDPR compliance and research question formulation.

        - In terms of legacy code management, the use of AI coding agents (such as Claude Code, Cursor AI, or OpenAI’s Codex) can assist with incremental code conversion and bug fixing. Developers should focus on context engineering, providing clear documentation, and dividing tasks into manageable subtasks for the agent. This approach is more effective than attempting large-scale code conversion in a single step. Consider using Claude Code’s sub-agents to create and delegate different tasks to sub-agents to efficiently manage the codebase conversion workflow. 

        - TechNova Oy’s internal technical expertise and ongoing proof-of-concept work provide a strong foundation for these initiatives. The team is encouraged to proceed step by step, starting with survey creation automation, followed by enhanced data analysis, and then exploring AI-assisted development tools for codebase conversion.

        - Regular validation and user feedback should be incorporated into the development cycle to ensure that new AI features meet user needs and deliver consistent value. If challenges arise during implementation, further consultation and support can be sought.

        - Overall, the focus should remain on practical integration of AI into core workflows, leveraging existing APIs, knowledge bases, and advanced LLMs to automate repetitive tasks, improve usability, and deliver actionable insights to users.

        ---
        **AI Maturity Levels:**

        Low:        Companies that are in the early stages of AI integration or
                    development and/or typically in the ideation phase and/or with
                    only a proof of concept. They have limited data, resources, and
                    expertise, and a minimal understanding of AI. AI is minimally or
                    not at all used in workflows, with no data management processes
                    or AI roadmap in place.

        Moderate:   Companies that are progressing in their AI journey, moving
                    beyond the proof of concept stage with functional solutions.
                    They have adequate data, resources, expertise, and understanding
                    of AI. AI is either fully or partially integrated into their
                    workflows, supported by established or developing data
                    management processes, and guided by a partially or fully
                    formulated AI roadmap.

        High:       Companies that have already developed advanced AI products and
                    have an established customer base. AI is fully or partially
                    integrated into their workflows, supported by established data
                    management processes, and guided by an AI roadmap. They require
                    assistance with specific technical details or when developing
                    new AI applications on top of their existing solutions.
        """


def generate_report_content(transcript: str, company_data: Dict[str, Any], 
                          meeting_notes: str = "", additional_instructions: str = "",
                          api_config: Dict[str, Any] = None) -> ReportResult:
    """
    Tool function to generate comprehensive consultation reports using the original 3-step process (3 API calls to LLM).

    Step 1: Generating main sections
    Step 2: Generation expert recommendations
    
    Args:
        transcript: Meeting transcript text
        company_data: Company information dictionary
        meeting_notes: Additional meeting notes (optional)
        additional_instructions: Special instructions (optional)
        api_config: API configuration dictionary
        
    Returns:
        ReportResult: Generated report with content and summary
    """
    if not transcript or not company_data:
        raise ValueError("Missing required inputs: transcript and company_data")
    
    print(f"Generating report for company: {company_data.get('company_name', 'Unknown')}")
    
    # Combine all context for the report (preserve original logic)
    full_context = "\nMEETING TRANSCRIPT:\n\n"
    full_context += transcript
    if meeting_notes:
        full_context += "\n\nADDITIONAL MEETING NOTES:\n" + meeting_notes
    
    if additional_instructions:
        full_context += "\n\n ADDITIONAL INSTRUCTIONS:\n\n" + additional_instructions

    if api_config.get('model','gpt-5.1').startswith("gpt-5"):
        full_context += "\n\n ADDITIONAL INSTRUCTIONS: \n\n" + """
        - Unless you are generating "Recommendation" section, do not create bulleted points and/or sub-sections in other sections. Avoid including unnecessary or overlapping details in the sections. Keep them concise, while covering all important details.
        - **VERY IMPORTANT:** If you are generating "Recommendation" section, strictly follow the format of the recommendations as given in the sample report. Create just one level of bullet points. DO NOT create any sub-points or sub-sections. 
        """
        
    # Generate the report using the 3-step process
    report_content = _generate_report(full_context, company_data, api_config)
    
    # Generate a report summary 
    report_summary = _extract_report_summary(report_content, api_config)
    
    print("Report generation completed successfully")
    
    return ReportResult(
        report_content=report_content,
        company_data=company_data,
        report_summary=report_summary
    )


def _generate_report(full_context: str, company_data: Dict[str, Any], 
                                         api_config: Dict[str, Any]) -> str:
    """Generate report content using the original 3-step process with exact prompts."""
    
    sample_report = """
        AI ASSESSMENT AND CONSULTATION

        Company Name: TechNova Oy

        Country: Finland

        Consultation Date: 11-03-2025

        Expert(s): Maria Rodriguez, Alex Chen

        Consultation Type: Regular

        **AI Maturity Level:**
        TechNova Oy is an established company that provides survey creation, distribution, and reporting tools for organizations and researchers. The platform supports both qualitative and quantitative data collection and analysis, with a focus on user experience and flexibility. The company has implemented production AI features, including Azure-based text analytics for sentiment analysis, summaries, and topic extraction. There is ongoing product development, including monthly releases and UI improvements. TechNova Oy has internal programming and AI expertise and has developed proof-of-concept solutions for AI integration. The company is actively experimenting with LLMs and has a knowledge base connected to its assistant. While full operationalization of AI into all core workflows is still in progress and some features remain in development, the presence of production AI capabilities and ongoing integration efforts align with a Moderate AI maturity level. 

        **Current Solution Development Stage:**
        TechNova Oy is in the prototyping and early implementation phase for AI features. The main objectives are to integrate AI into survey creation and reporting. The company has a working proof-of-concept for AI-generated surveys and uses Azure AI for text analytics. However, full integration of AI into the user interface and automation of survey creation are still under development. The reporting module is being enhanced to support more advanced AI-driven analysis of quantitative data. TechNova Oy aims to reduce manual work, improve user onboarding, and provide actionable insights through AI. The company is seeking practical solutions for connecting AI outputs directly to survey creation and for automating data analysis tasks.

        **Validity of Concept and Authenticity of Problem Addressed:**
        The proposed AI concepts address genuine user needs in survey creation and data analysis. Customers have requested AI features to simplify survey design and to gain deeper insights from survey results. The integration of AI into these workflows is practical and aligns with current trends in survey platforms. The scope is clear, focusing on automating repetitive tasks and improving usability. The feasibility is supported by existing technical resources and preliminary experiments, though further development is needed for seamless integration.

        **Integration and Importance of AI in the Idea:**
        AI is central to the planned improvements in both survey creation and reporting. It is intended to automate the generation of survey questions, provide recommendations, and analyze both qualitative and quantitative data. AI will act as an assistant to guide users, reduce manual effort, and enhance the overall functionality of the platform. 

        **Identified Target Market and Customer Segments:**
        TechNova Oy targets organizations, researchers, and thesis writers who require flexible survey tools and advanced reporting capabilities. The market is clearly defined, with a focus on users who benefit from automated survey creation and data analysis. The relevance of the target segments is confirmed by direct customer requests and feedback.

        **Data Requirement Assessment:**
        The company requires structured data in the form of survey templates to be suggested to the users through AI. TechNova Oy has a general understanding of its data needs, supported by an existing knowledge base and survey library. However, there is a need for greater clarity regarding the specific requirements, particularly in the context of AI integration. The process for integrating survey templates into the AI context must be clearly defined to ensure these sources are effectively utilized. 

        **Data Collection Strategy:**
        TechNova Oy collects data through its survey platform, allowing users to create and distribute surveys and gather responses. The system supports exporting data to formats like Excel. There is an established process for storing survey templates and user-generated questions. Currently, these data collection processes are designed primarily to support survey operations and reporting, rather than for AI training or context enrichment. As such, there is no structured plan in place for collecting data specifically to support new AI-driven features. This represents an area that requires further development, and it is recommended that a dedicated data collection strategy be established to ensure the effective implementation of AI capabilities. 

        **Technical Expertise and Capability:**
        TechNova Oy has internal expertise in programming and foundational AI concepts. The CTO has developed proof-of-concept solutions for AI integration, and the team is familiar with LLMs and API-based workflows. However, the team’s experience with advanced AI integration and context engineering is still developing, and current capabilities are primarily at the POC and early implementation stage. The company’s internal expertise does not yet extend to advanced user interface design, robust context management, or seamless integration of AI outputs with core systems. As a result, while TechNova Oy is capable of implementing new AI features at a basic level, achieving full AI productization and advanced integration may require upskilling and/or external support.

        **Expectations from FAIR Services:**
        TechNova Oy expects practical guidance on integrating AI into its survey creation and reporting modules. The company seeks recommendations for integrating AI-generated outputs into the user interface, automating data analysis, and enhancing legacy code management. Support in selecting appropriate AI models, structuring API calls, and validating outputs is also anticipated.

        **Recommendations:**
        - TechNova Oy is advised to prioritize the integration of AI-driven survey creation within the existing user interface. The recommended approach is to use a retrieval-augmented generation (RAG) system to provide relevant context from the knowledge base, including customer documents and historical surveys, to a large language model (LLM). The LLM should generate survey questions in a structured format, such as JSON, which can be directly parsed and imported into the survey editor. This will eliminate manual copy-paste steps and streamline the workflow for users.

        - The company should explore advanced LLMs such as OpenAI’s GPT-5 and Anthropic’s Claude-Sonnet-4 or Claude-Opus-4.1 for both survey generation and code creation tasks. These models can be prompted to produce structured outputs and simple API call code.

        - Connecting the AI assistant to the existing REST API system is a practical next step. By enabling the LLM to make API calls based on user prompts, survey creation and editing can be automated. Setting up an MCP (Model Context Protocol) service that understands the API endpoints will allow the LLM to perform actions such as creating, modifying, and managing surveys directly from the chat interface.

        - For reporting and data analysis, TechNova Oy should identify the most common and recurring analysis questions from users, such as demographic breakdowns and response distributions. A library of analysis code snippets should be developed for these tasks. This allows some flexibility, determinism and cost-efficiency and guards against LLM errors compared to a situation where LLM would create analyses from scratch. The LLM can select and execute the appropriate code based on user queries, ensuring consistent and reliable results. For less frequent or unpredictable questions, direct LLM-based analysis can be used, with mechanisms of validation to minimize errors and hallucinations.

        - The company should continue to use Microsoft Azure AI services for text analytics but expand capabilities to include more nuanced sentiment analysis, entity recognition, and quantitative data summaries. Testing LLMs with a wide range of user questions and data types is recommended to assess accuracy and consistency before full deployment.

        - To improve onboarding and support for new users, consider adding AI-powered suggestions for survey types, consent questions, and best practices directly within the survey creation flow. This will lower the threshold for first-time users and help address common challenges, such as GDPR compliance and research question formulation.

        - In terms of legacy code management, the use of AI coding agents (such as Claude Code, Cursor AI, or OpenAI’s Codex) can assist with incremental code conversion and bug fixing. Developers should focus on context engineering, providing clear documentation, and dividing tasks into manageable subtasks for the agent. This approach is more effective than attempting large-scale code conversion in a single step. Consider using Claude Code’s sub-agents to create and delegate different tasks to sub-agents to efficiently manage the codebase conversion workflow. 

        - TechNova Oy’s internal technical expertise and ongoing proof-of-concept work provide a strong foundation for these initiatives. The team is encouraged to proceed step by step, starting with survey creation automation, followed by enhanced data analysis, and then exploring AI-assisted development tools for codebase conversion.

        - Regular validation and user feedback should be incorporated into the development cycle to ensure that new AI features meet user needs and deliver consistent value. If challenges arise during implementation, further consultation and support can be sought.

        - Overall, the focus should remain on practical integration of AI into core workflows, leveraging existing APIs, knowledge bases, and advanced LLMs to automate repetitive tasks, improve usability, and deliver actionable insights to users.

        ---
        **AI Maturity Levels:**

        Low:        Companies that are in the early stages of AI integration or
                    development and/or typically in the ideation phase and/or with
                    only a proof of concept. They have limited data, resources, and
                    expertise, and a minimal understanding of AI. AI is minimally or
                    not at all used in workflows, with no data management processes
                    or AI roadmap in place.

        Moderate:   Companies that are progressing in their AI journey, moving
                    beyond the proof of concept stage with functional solutions.
                    They have adequate data, resources, expertise, and understanding
                    of AI. AI is either fully or partially integrated into their
                    workflows, supported by established or developing data
                    management processes, and guided by a partially or fully
                    formulated AI roadmap.

        High:       Companies that have already developed advanced AI products and
                    have an established customer base. AI is fully or partially
                    integrated into their workflows, supported by established data
                    management processes, and guided by an AI roadmap. They require
                    assistance with specific technical details or when developing
                    new AI applications on top of their existing solutions.
        """
    
    # Step 1: Generate main sections 
    main_sections = _generate_main_sections(full_context, company_data, sample_report, api_config)
    
    # Step 2: Generate recommendations section 
    recommendations_section = _generate_recommendations_section(full_context, company_data, sample_report, api_config, main_sections)
    
    # Combine all sections
    complete_report = f"""{main_sections}

{recommendations_section}

"""
    
    return complete_report


def _generate_main_sections(full_context, company_data, sample_report, api_config):
    """Generate main sections."""
    
    prompt = f"""
    You are an AI advisor generating a professional post-consultancy report for a company after conducting a detailed AI needs analysis. Use the provided meeting context to write the report. The report must strictly follow the structure, format, and language style of the attached sample report.

    IMPORTANT CONSIDERATIONS: 
    1. The context may comprises a meeting transcript (mendatory) labelled as "MEETING TRANSCRIPT:", the notes taken by the AI experts (optional) labelled as 'ADDITIONAL MEETING NOTES:', and some additional instructions (optional) labelled as "ADDITIONAL INSTRUCTIONS:". 
    2. Meeting transcript contains conversation between AI experts and company representatives. Most of the questions in the transcript will be from the AI experts, and the answers will be from company representatives. 
    3. There could be some questions from the company representatives too, but they may be more focused on the services they are looking for.
    4. Some parts of the 'ADDITIONAL MEETING NOTES:' might be in some other language, such as Finnish. However, you have to consider the whole meeting context and generate report in English.  
    
    **VERY IMPORTANT:**
    -**Do not make up anything. Generate report only from the provided context. If the information about some fields are not explicitly mentioned or implicitly deducible, output 'n/a'.** 
    -**Use simple language without any fluff and em dash (—).**
    -**Maintain a neutral and professional tone.**

    FORMAT REQUIREMENTS: The final report must exactly follow this non-tabular format:
    1. Title "AI ASSESSMENT AND CONSULTATION" at the top
    2. Company information in a series of lines: Company Name, Country, Consultation Date, Expert(s), Customer manager, and Consultation Type
    3. A series of sections with bold headings followed by descriptive content. Use title case for the headings, where major words are capitalized, but short conjunctions, prepositions, and articles (such as "and," "to," "the," "from," "for," and "a", etc.) are not capitalized unless they are the first word.

    LANGUAGE GUIDELINES - AVOID THE FOLLOWING:
    1. Formal, robotic tone and predictable sentence structures
    2. Repetitive phrasing and redundancy of words or ideas
    3. Overuse of generic, high-frequency words and phrases such as:
        - Delve into, Underscore, Pivotal, Realm, Harness, Illuminate, Foster, Explore, Leverage, Streamline, Modernize, Vital, Comprehensive, Ultimately, Firstly, In conclusion, Valuable, Boost, Drive, Finally
    4. Use of metaphors or phrases like "tapestry," "deep dive," or "showcasing"
    5. Do not mention the given "context" or "transcript" in the report.

    CONTENT GUIDELINES:
    - Make the most of all relevant information provided in the meeting context
    - Create a comprehensive, detailed report without omitting important details
    - Use direct language that precisely communicates facts and insights
    - Vary sentence structures naturally to maintain reader engagement
    - Use domain-specific terminology where appropriate, but avoid jargon when simpler terms work
    
    Include the following company details:
    Company Name: {company_data.get('company_name', 'Unknown')}
    Country: {company_data.get('country', 'Unknown')}
    Consultation Date: {company_data.get('consultation_date', 'Unknown')}
    Expert(s): {company_data.get('experts', 'Unknown')}
    Customer manager: {company_data.get('customer_manager', 'Unknown')}
    Consultation Type: {company_data.get('consultation_type', 'Unknown')}
    
    Generate ONLY the following sections with EXACTLY these headings:

    1. **AI Maturity Level:**
    - Briefly describe the company's current business operations and services offered. 
    - Describe their current AI maturity and classify as Low, Moderate, or High. Base this on their development stage, data availability, technical expertise, workflow integration, and AI roadmap. If this information is explicitly present in the context, use it verbatim. 

    2. **Current Solution Development Stage:**
    - Explain if they are in ideation, prototyping, implementation phase, or already has an AI product with customer base.
    - Describe the current state of development, and company's AI readiness with what exists and what needs development.
    - Describe what they are currently looking for, and their aims and objectives for AI implementation.

    3. **Validity of Concept and Authenticity of Problem Addressed:**
    - Assess the practicality and the innovation level of the proposed AI concept, and if it solves a genuine problem
    - Comment on feasibility and scope

    4. **Integration and Importance of AI in the Idea:**
    - Describe how central AI is to the company's proposed solution and its significance in solving the problem. 
    - Do not mention any specific AI methods or technologies. 

    5. **Identified Target Market and Customer Segments:**
    - State their target customers
    - Evaluate how clearly defined and relevant the market is

    6. **Data Requirement Assessment:**
    - State the type of data required for the AI implementation (if mentioned in the context)
    - State whether the company currently has the data required for the AI implementation? If yes, what? If not, what data is actually required?

    7. **Data Collection Strategy:**
    - State whether the company has any strategy for collecting, storing, and using data? If yes, describe it. 

    8. **Technical Expertise and Capability:**
    - Assess their technical skills and development ability

    9. **Expectations from FAIR Services:**
    - Describe what they expect from the consultation

    Here is the example report format to follow (VERY IMPORTANT):
    {sample_report}
    
    Use this meeting context to generate the report:
    \"\"\"
    {full_context}
    \"\"\"
            
    Generate only the sections listed above following the exact format from the example. Keep language business-focused, concise, and professional. Do NOT include Recommendations sections.
    
    IMPORTANT: Provide your response as plain text without any markdown code blocks (no ``` or similar formatting).
    """
    
    return _call_llm(prompt, api_config, temperature=0.0)


def _generate_recommendations_section(full_context, company_data, sample_report, api_config, main_sections):
    """Generate recommendations section using original prompt."""
    
    prompt = f"""
    You are an AI advisor generating the Recommendations section for a professional post-consultancy report. Use the provided meeting context to write this specific section. The section must strictly follow the structure, format, and language style of the attached sample report.

    IMPORTANT CONSIDERATIONS: 
    1. The context may comprises a meeting transcript (mendatory) labelled as "MEETING TRANSCRIPT:", the notes taken by the AI experts (optional) labelled as 'ADDITIONAL MEETING NOTES:', and some additional instructions (optional) labelled as "ADDITIONAL INSTRUCTIONS:". 
    2. Meeting transcript contains conversation between AI experts and company representatives. Most of the questions in the transcript will be from the AI experts, and the answers will be from company representatives. 
    3. There could be some questions from the company representatives too, but they may be more focused on the services they are looking for.
    4. Some parts of the 'ADDITIONAL MEETING NOTES:' might be in some other language, such as Finnish. However, you have to consider the whole meeting context and generate report in English.  
    
    **VERY IMPORTANT:**
    -**Do not make up anything. Generate recommendations only from the given context. If no recommendations are present, indicate this clearly.** 
    -**Use simple language without any fluff and em dash (—).**
    -**Maintain a neutral and professional tone.**

    LANGUAGE GUIDELINES - AVOID THE FOLLOWING:
    1. Formal, robotic tone and predictable sentence structures
    2. Repetitive phrasing and redundancy of words or ideas
    3. Overuse of generic, high-frequency words and phrases such as:
        - Delve into, Underscore, Pivotal, Realm, Harness, Illuminate, Foster, Explore, Leverage, Streamline, Modernize, Vital, Comprehensive, Ultimately, Firstly, In conclusion, Valuable, Boost, Drive, Finally
    4. Use of metaphors or phrases like "tapestry," "deep dive," or "showcasing"
    5. Do not mention the given "context" or "transcript" in the report.

    CONTENT GUIDELINES:
    - Make the most of all relevant information provided in the meeting context
    - Create a comprehensive, detailed section without omitting important details
    - Use direct language that precisely communicates facts and insights
    - Vary sentence structures naturally to maintain reader engagement
    - Use domain-specific terminology where appropriate, but avoid jargon when simpler terms work
    
    Company Context:
    Company Name: {company_data.get('company_name', 'Unknown')}
    Country: {company_data.get('country', 'Unknown')}
    Consultation Date: {company_data.get('consultation_date', 'Unknown')}
    Expert(s): {company_data.get('experts', 'Unknown')}
    Customer manager: {company_data.get('customer_manager', 'Unknown')}
    Consultation Type: {company_data.get('consultation_type', 'Unknown')}
    
    Generate ONLY the following section with EXACTLY this heading:

    **Recommendations:**
    - **Very Important: ** The recommendations are to be generated only from the given context. DO NOT make up any recommendations.
    - Provide a blend of comprehensive discussions, reflections, suggestions, observations, and actionable points.
    - The tone should not be purely commanding or advisory but rather a mix of thoughtful analysis and practical guidance
    - Include relevant technical and business perspectives
    - Use a conversational yet professional tone
    - Make recommendations specific, insightful, and tailored to the company's unique situation
    - Make sure the recommendations are comprehensive and cover everything AI experts recommended in the transcript and the meeting notes. Make sure that no opinion, suggestion, or recommendation present in the overall context is left out.

    Here is the example report format to follow (VERY IMPORTANT):
    {sample_report}
    
    Use this meeting context to generate the recommendations:
    \"\"\"
    {full_context}
    \"\"\"
    
    REPORT SECTIONS ALREADY GENERATED:
    {main_sections}
            
    Generate only the Recommendations section following the exact format from the example. Keep language business-focused, concise, and professional.
    
    IMPORTANT: Provide your response as plain text without any markdown code blocks (no ``` or similar formatting).
    """
    
    return _call_llm(prompt, api_config, temperature=0.0)


def _extract_report_summary(report_content: str, api_config: Dict[str, Any]) -> str:
    """Extract a summary using original method."""
    
    lines = report_content.strip().split('\n')
    summary_lines = []
    
    for line in lines:
        if line.strip() and not line.startswith('**') and not line.startswith('#'):
            # Take first few content lines as summary
            summary_lines.append(line.strip())
            if len(summary_lines) >= 3:
                break
    
    return ' '.join(summary_lines)[:500] + "..." if len(' '.join(summary_lines)) > 500 else ' '.join(summary_lines)


def _call_llm(prompt: str, api_config: Dict[str, Any], max_tokens: int = 16000, temperature: float = 0.0) -> str:
    """Make LLM API call using original configuration."""
    
    if not api_config:
        raise ValueError("API configuration is required")
    
    if api_config.get('use_azure', False):
        client = AzureOpenAI(
            api_key=api_config.get('api_key',''),
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
    import re
    
    # Remove standalone code block markers
    content = re.sub(r'^```[a-zA-Z]*\n', '', content, flags=re.MULTILINE)
    content = re.sub(r'^```\s*$', '', content, flags=re.MULTILINE)
    
    # Remove code blocks that wrap entire sections
    content = re.sub(r'```\s*\n(.*?)\n```', r'\1', content, flags=re.DOTALL)
    
    # Clean up any extra whitespace created by removal
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)

    return content.strip()