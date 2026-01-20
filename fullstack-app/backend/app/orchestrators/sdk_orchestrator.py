"""
Procedural orchestrator for the AI report generation workflow.
This implements a sequential workflow using SDK-style functions for each step.
"""

import os
import re
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from app.agents.transcription_agent import transcribe_audio_file
from app.agents.report_agent import generate_report_content, get_sample_report
from app.agents.verification_agent import verify_report_content
from app.agents.revision_agent import revise_report_content


class SDKOrchestrator:
    """
    Orchestrates the multi-agent AI report generation workflow using a procedural approach.
    This implements a sequential workflow with verification-revision cycles using SDK-style functions.
    """
    
    def __init__(self, api_config: Dict[str, Any], verification_rounds: int = 3):
        """Initialize the SDK orchestrator with API configuration."""
        self.api_config = api_config
        self.verification_rounds = max(1, min(verification_rounds, 3))

        print(f"SDK orchestrator initialized with {self.verification_rounds} verification rounds")
    
    def process_recording(self, file_path: str, output_dir: str, company_data: Dict[str, Any], 
                         meeting_notes: str = "", additional_instructions: str = "", compress_audio: bool = True,
                         progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Process an audio/video recording through the complete workflow.
        Maintains original orchestrator workflow logic using SDK functions.
        """
        try:
            print(f"Starting SDK workflow for recording: {os.path.basename(file_path)}")
            
            # Step 1: Transcription using SDK function
            print("Step 1: Transcribing audio file...")
            self._emit_progress(progress_callback, 'analysis', 'start', 'Transcribing recording...')
            transcription_result = transcribe_audio_file(file_path, output_dir, self.api_config, compress_audio)
            transcript = transcription_result.transcript
            transcript_path = transcription_result.transcript_path
            
            # Continue with transcript processing
            return self._process_transcript_internal(
                transcript, output_dir, company_data, meeting_notes, 
                additional_instructions, transcript_path, progress_callback, analysis_started=True
            )
            
        except Exception as e:
            print(f"Workflow failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'company_data': company_data,
                'verification_history': [],
                'revision_history': [],
                'final_report': None
            }
    
    def process_transcript(self, transcript: str, output_dir: str, company_data: Dict[str, Any], 
                          meeting_notes: str = "", additional_instructions: str = "",
                          progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Process an existing transcript through the workflow.
        """
        try:
            print("Starting SDK workflow with existing transcript")

            # Continue with transcript processing
            return self._process_transcript_internal(
                transcript, output_dir, company_data, meeting_notes, 
                additional_instructions, None, progress_callback
            )
            
        except Exception as e:
            print(f"Workflow failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'company_data': company_data,
                'verification_history': [],
                'revision_history': [],
                'final_report': None
            }
    
    def _process_transcript_internal(self, transcript: str, output_dir: str, 
                                   company_data: Dict[str, Any], meeting_notes: str, 
                                   additional_instructions: str, transcript_path: str,
                                   progress_callback: Optional[Callable[[Dict[str, Any]], None]],
                                   analysis_started: bool = False) -> Dict[str, Any]:
        """Internal method to process the transcript and generate the report using SDK functions."""
        
        print("Processing transcript through SDK workflow...")
        verification_history = []
        revision_history = []
        
        try:
            if not analysis_started:
                self._emit_progress(progress_callback, 'analysis', 'start', 'Analyzing transcript context...')
            # Step 2: Generate initial report using SDK function
            self._emit_progress(progress_callback, 'analysis', 'complete', 'Transcript analyzed.')
            self._emit_progress(progress_callback, 'report_generation', 'start', 'Generating draft report...')
            print("Step 2: Generating initial report...")
            report_result = generate_report_content(
                transcript, company_data, meeting_notes, additional_instructions, self.api_config
            )
            current_report = report_result.report_content
            print("Initial report generation completed")
            self._emit_progress(progress_callback, 'report_generation', 'complete', 'Initial report ready.')
            
            # Step 3: Verification and revision cycle
            verification_round = 1
            max_rounds = self.verification_rounds
            
            while verification_round <= max_rounds:
                print(f"Step 3.{verification_round}: Verification round {verification_round}")
                
                # Execute verification using SDK function
                # Prepare context for verification round
                previous_verifications = [v for v in verification_history if v.get('round', 0) < verification_round]
                previous_revisions = [r.get('revision_notes', '') for r in revision_history if r.get('round', 0) < verification_round]
                
                # Enhanced context logging
                if previous_verifications:
                    total_prev_issues = sum(len(v.get('issues', [])) for v in previous_verifications)
                    print(f"Context memory: {len(previous_verifications)} previous rounds with {total_prev_issues} total issues")
                if previous_revisions:
                    print(f"Revision context: {len([r for r in previous_revisions if r])} revision notes available")
                
                # Execute context-aware verification with sample report for format checking
                step_name = f'verification_{verification_round}'
                self._emit_progress(progress_callback, step_name, 'start', f'Running verification round {verification_round}...')
                sample_report = get_sample_report()
                verification_result = verify_report_content(
                    current_report, transcript, meeting_notes, additional_instructions, 
                    verification_round, self.api_config,
                    previous_verification_results=previous_verifications,
                    previous_revision_notes=previous_revisions,
                    sample_report=sample_report
                )
                self._emit_progress(progress_callback, step_name, 'complete', f'Completed verification round {verification_round}.')
                
                # Extract verification details
                needs_revision = verification_result.needs_revision
                score = verification_result.score
                issues = [issue.dict() if hasattr(issue, 'dict') else issue for issue in verification_result.issues]
                suggestions = verification_result.suggestions  
                
                # Store verification results
                verification_history.append({
                    'round': verification_round,
                    'score': score,
                    'issues': issues,
                    'needs_revision': needs_revision,
                    'summary': verification_result.summary,
                    'strengths': verification_result.strengths,
                    'decision_explanation': verification_result.decision_explanation
                })
                
                print(f"\n=== VERIFICATION ROUND {verification_round} RESULTS ===")
                print(f"Score: {score}/10")
                print(f"Issues found: {len(issues)}")
                print(f"Needs revision: {needs_revision}")
                if verification_round > 1 and previous_verifications:
                    prev_issues = len(previous_verifications[-1].get('issues', []))
                    trend = "↓" if len(issues) < prev_issues else "↑" if len(issues) > prev_issues else "→"
                    print(f"Issue trend: {prev_issues} → {len(issues)} {trend}")
                print(f"Decision: {verification_result.decision_explanation}")
                print("=" * 50)
                
                if not needs_revision:
                    print(f"Report verification passed on round {verification_round}!")
                    break

                # If revision is needed and we haven't exceeded max rounds
                if verification_round <= max_rounds:
                    print(f"Step 3.{verification_round}.1: Revising report based on feedback...")
                    revision_step = f'revision_{verification_round}'
                    self._emit_progress(progress_callback, revision_step, 'start', f'Applying revisions for round {verification_round}...')
                    
                    # Execute revision using SDK function - include suggestions
                    revision_result = revise_report_content(
                        current_report, 
                        {
                            'issues': issues, 
                            'suggestions': suggestions, 
                            'summary': verification_result.summary, 
                            'score': score
                        },
                        company_data, 
                        transcript, 
                        verification_round, 
                        self.api_config
                    )
                    
                    # Update the current report
                    current_report = revision_result.revised_report
                    self._emit_progress(progress_callback, revision_step, 'complete', f'Completed revisions for round {verification_round}.')
                    
                    # Store revision results
                    revision_history.append({
                        'round': verification_round,
                        'issues_addressed': revision_result.issues_addressed,
                        'suggestions_implemented': revision_result.suggestions_implemented,
                        'revision_notes': revision_result.revision_notes,
                        'revision_summary': revision_result.revision_summary
                    })
                    
                    print(f"Revision round {verification_round} completed")
                
                verification_round += 1
            
            # Step 4: Save final report
            print("Step 4: Finalizing and saving report...")
            self._emit_progress(progress_callback, 'finalization', 'start', 'Saving final report...')
            os.makedirs(output_dir, exist_ok=True)
            doc_path = self._ensure_report_saved(current_report, output_dir, company_data)
            self._emit_progress(progress_callback, 'finalization', 'complete', 'Report finalized.')
            
            final_report = {
                'content': current_report,
                'doc_path': doc_path,
            }
            
            workflow_results = {
                'status': 'success',
                'company_data': company_data,
                'verification_history': verification_history,
                'revision_history': revision_history,
                'final_report': final_report,
                'final_report_content': current_report,
                'final_report_path': doc_path,
                'transcript_path': transcript_path  
            }
            
            # Add individual verification results for compatibility
            for i, ver_result in enumerate(verification_history, 1):
                workflow_results[f'verification_{i}_results'] = ver_result
            
            # Add individual revision results for compatibility
            for i, rev_result in enumerate(revision_history, 1):
                workflow_results[f'revision_{i}_results'] = rev_result
            
            print("SDK workflow completed successfully")
            return workflow_results
            
        except Exception as e:
            error_msg = f"SDK workflow failed: {str(e)}"
            print(error_msg)
            
            return {
                'status': 'failed',
                'error': error_msg,
                'company_data': company_data,
                'verification_history': verification_history,
                'revision_history': revision_history,
                'final_report': None,
                'transcript_path': transcript_path  
            }

    @staticmethod
    def _emit_progress(callback: Optional[Callable[[Dict[str, Any]], None]], step: str,
                       status: str, message: Optional[str] = None) -> None:
        """Safely emit progress updates without breaking the workflow."""
        if not callback:
            return
        try:
            callback({
                'step': step,
                'status': status,
                'message': message
            })
        except Exception as err:
            print(f"Progress callback failed for step '{step}': {err}")
    
    def _ensure_report_saved(self, report_content: str, output_dir: str, company_data: Dict[str, Any]) -> str:
        """Ensure the report is saved in DOCX format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company_name_safe = re.sub(r'[^\w\s-]', '', company_data.get('company_name', 'Unknown')).strip().replace(' ', '_')
        base_filename = f"{company_name_safe}"
        
        # Save as DOCX using formatter
        doc_path = os.path.join(output_dir, f"{base_filename}.docx")
        try:
            from app.formatting.formatter import create_word_doc
            create_word_doc(report_content, doc_path, company_data)
            print(f"DOCX report saved to {doc_path}")
            return doc_path
        except Exception as e:
            print(f"Failed to save DOCX: {str(e)}")
            return None


def create_sdk_orchestrator(api_config: Dict[str, Any], verification_rounds: int = 3) -> SDKOrchestrator:
    """
    Factory function to create SDK orchestrator.
    
    Args:
        api_config: API configuration dictionary
        verification_rounds: Number of verification rounds (1-3)
        
    Returns:
        SDKOrchestrator: Configured orchestrator instance
    """
    return SDKOrchestrator(api_config, verification_rounds)
