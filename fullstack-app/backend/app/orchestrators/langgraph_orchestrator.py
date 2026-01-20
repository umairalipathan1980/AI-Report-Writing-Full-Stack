#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LangGraph-based Orchestrator for V6 AI Consultancy Report Generation.
Implements the same generation-verification-revision workflow as the procedural system,
but using LangGraph's state machine for agentic workflow management.
"""

import os
import re
from typing import Dict, Any, List, Optional, TypedDict, Callable
from datetime import datetime
from langgraph.graph import StateGraph, END


def notify_progress(state: "WorkflowState", step: str, status: str,
                    message: Optional[str] = None) -> None:
    """Send progress updates back to the caller when available."""
    callback = state.get('progress_callback')
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


# ========================================
# State Schema
# ========================================

class WorkflowState(TypedDict):
    """
    State maintained throughout the LangGraph workflow for V6.
    This matches the procedural workflow's state tracking but in a structured format.
    """
    # Input data (immutable throughout workflow)
    audio_file_path: Optional[str]        # If processing recording
    transcript: Optional[str]             # If processing existing transcript
    output_dir: str
    company_data: Dict[str, Any]
    meeting_notes: str
    additional_instructions: str
    compress_audio: bool
    api_config: Dict[str, Any]
    progress_callback: Optional[Callable[[Dict[str, Any]], None]]

    # Workflow configuration
    verification_rounds: int              # max rounds

    # Processed data
    transcript_path: Optional[str]        # Saved transcript path

    # Report tracking
    current_report: str
    report_history: List[str]

    # Verification tracking
    verification_round: int
    verification_history: List[Dict[str, Any]]

    # Revision tracking
    revision_history: List[Dict[str, Any]]

    # Workflow control
    needs_revision: bool
    status: str
    error_message: Optional[str]
    last_verification_result: Optional[Any]

    # Final outputs
    final_report_content: str
    final_report_path: str
    sample_report: Optional[str]


# ========================================
# Node Functions
# ========================================

def transcribe_audio_node(state: WorkflowState) -> WorkflowState:
    """
    Node 1: Transcribe audio/video file.
    Only executes if audio_file_path is provided.
    """
    print("\n" + "="*70)
    print("🎤 NODE 1: TRANSCRIPTION")
    print("="*70)

    try:
        from app.agents.transcription_agent import transcribe_audio_file

        audio_file = state.get('audio_file_path')
        transcript_present = state.get('transcript')
        if audio_file:
            notify_progress(state, 'analysis', 'start', 'Transcribing recording...')
        elif transcript_present:
            notify_progress(state, 'analysis', 'start', 'Analyzing provided transcript...')
        if not audio_file:
            # Skip transcription, use existing transcript
            print("⏭️  Skipping transcription - using provided transcript")
            print("="*70)
            notify_progress(state, 'analysis', 'complete', 'Transcript ready for analysis.')
            return {
                **state,
                'status': 'transcription_skipped'
            }

        print(f"🤖 Orchestrator invoking Transcription agent...")
        print(f"📁 File: {os.path.basename(audio_file)}")
        print(f"⚙️  Compress audio: {state.get('compress_audio', True)}")

        # Execute transcription
        result = transcribe_audio_file(
            audio_file,
            state['output_dir'],
            state['api_config'],
            state.get('compress_audio', True)
        )

        print(f"\n✅ Transcription complete!")
        print(f"   └─ Transcript: {len(result.transcript)} characters")
        print(f"   └─ Saved to: {result.transcript_path}")
        print("="*70)
        notify_progress(state, 'analysis', 'complete', 'Transcript ready for analysis.')

        return {
            **state,
            'transcript': result.transcript,
            'transcript_path': result.transcript_path,
            'status': 'transcribed'
        }

    except Exception as e:
        print(f"\n❌ ERROR in transcription: {str(e)}")
        print("="*70)
        notify_progress(state, 'analysis', 'complete', 'Transcription failed.')
        return {
            **state,
            'status': 'error',
            'error_message': f'Transcription failed: {str(e)}'
        }


def generate_report_node(state: WorkflowState) -> WorkflowState:
    """
    Node 2: Generate initial AI consultancy report.
    Wraps generate_report_content()
    """
    print("\n" + "="*70)
    print("✍️  NODE 2: REPORT GENERATION")
    print("="*70)
    print(f"🤖 Orchestrator invoking Report Generation agent...")

    try:
        from app.agents.report_agent import generate_report_content

        notify_progress(state, 'report_generation', 'start', 'Generating draft report...')
        # Execute report generation
        result = generate_report_content(
            state['transcript'],
            state['company_data'],
            state.get('meeting_notes', ''),
            state.get('additional_instructions', ''),
            state['api_config']
        )

        print(f"\n✅ Report generation complete!")
        print(f"   └─ Report: {len(result.report_content)} characters")
        print("="*70)

        notify_progress(state, 'report_generation', 'complete', 'Initial report ready.')
        return {
            **state,
            'current_report': result.report_content,
            'report_history': [result.report_content],
            'status': 'report_generated'
        }

    except Exception as e:
        print(f"\n❌ ERROR in report generation: {str(e)}")
        print("="*70)
        notify_progress(state, 'report_generation', 'complete', 'Report generation failed.')
        return {
            **state,
            'status': 'error',
            'error_message': f'Report generation failed: {str(e)}'
        }


def verify_report_node(state: WorkflowState) -> WorkflowState:
    """
    Node 3: Verify report quality and compliance.
    Wraps verify_report_content()
    """
    round_num = state.get('verification_round', 1)

    print("\n" + "="*70)
    print(f"🔍 NODE 3: VERIFICATION (Round {round_num}/{state['verification_rounds']})")
    print("="*70)
    print(f"🤖 Orchestrator invoking Verification agent...")

    try:
        from app.agents.report_agent import get_sample_report
        from app.agents.verification_agent import verify_report_content

        # Prepare context
        previous_verifications = [
            v for v in state['verification_history']
            if v.get('round', 0) < round_num
        ]
        previous_revisions = [
            r.get('revision_notes', '')
            for r in state['revision_history']
            if r.get('round', 0) < round_num
        ]

        # Enhanced context logging
        if previous_verifications:
            total_prev_issues = sum(len(v.get('issues', [])) for v in previous_verifications)
            print(f"Context memory: {len(previous_verifications)} previous rounds with {total_prev_issues} total issues")
        if previous_revisions:
            print(f"Revision context: {len([r for r in previous_revisions if r])} revision notes available")

        # Get sample report for format checking
        sample_report = get_sample_report()

        # Execute verification
        notify_progress(state, f'verification_{round_num}', 'start', f'Running verification round {round_num}...')
        result = verify_report_content(
            state['current_report'],
            state['transcript'],
            state.get('meeting_notes', ''),
            state.get('additional_instructions', ''),
            round_num,
            state['api_config'],
            previous_verification_results=previous_verifications,
            previous_revision_notes=previous_revisions,
            sample_report=sample_report
        )

        # Extract verification details
        issues = [issue.dict() if hasattr(issue, 'dict') else issue
                  for issue in result.issues]

        # Store verification result
        verification_entry = {
            'round': round_num,
            'score': result.score,
            'issues': issues,
            'needs_revision': result.needs_revision,
            'summary': result.summary,
            'strengths': result.strengths,
            'decision_explanation': result.decision_explanation
        }

        print(f"\n📊 VERIFICATION RESULTS:")
        print(f"   ├─ Score: {result.score}/10")
        print(f"   ├─ Issues: {len(issues)}")
        print(f"   └─ Decision: {'⚠️  Needs revision' if result.needs_revision else '✅ Approved'}")

        # Print issue trend if not first round
        if round_num > 1 and previous_verifications:
            prev_issues = len(previous_verifications[-1].get('issues', []))
            trend = "↓" if len(issues) < prev_issues else "↑" if len(issues) > prev_issues else "→"
            print(f"   └─ Issue trend: {prev_issues} → {len(issues)} {trend}")

        print(f"Decision: {result.decision_explanation}")
        print(f"🔀 Orchestrator routing to: {'Revision Agent' if result.needs_revision else 'Save Report'}")
        print("="*70)
        notify_progress(state, f'verification_{round_num}', 'complete', f'Completed verification round {round_num}.')

        return {
            **state,
            # DO NOT increment round here - matches procedural logic where round increments AFTER revise
            'verification_history': state['verification_history'] + [verification_entry],
            'needs_revision': result.needs_revision,
            'last_verification_result': result,
            'status': 'verified'
        }

    except Exception as e:
        print(f"\n❌ ERROR in verification: {str(e)}")
        print("="*70)
        notify_progress(state, f'verification_{round_num}', 'complete', f'Verification failed in round {round_num}.')
        return {
            **state,
            'status': 'error',
            'error_message': f'Verification failed: {str(e)}'
        }


def revise_report_node(state: WorkflowState) -> WorkflowState:
    """
    Node 4: Revise report based on verification feedback.
    Wraps revise_report_content()
    """
    # After fix: verification doesn't increment, so use current round directly
    round_num = state.get('verification_round', 1)  # Current revision round

    print("\n" + "="*70)
    print(f"🔧 NODE 4: REVISION (Round {round_num})")
    print("="*70)
    print(f"🤖 Orchestrator invoking Revision agent...")

    try:
        from app.agents.revision_agent import revise_report_content

        # Get last verification result
        last_verification = state['last_verification_result']
        issues = [issue.dict() if hasattr(issue, 'dict') else issue
                  for issue in last_verification.issues]

        # Prepare verification dict for revision agent
        verification_dict = {
            'issues': issues,
            'suggestions': last_verification.suggestions,
            'summary': last_verification.summary,
            'score': last_verification.score
        }

        print(f"   ├─ Issues to address: {len(issues)}")
        print(f"   └─ Suggestions to implement: {len(last_verification.suggestions)}")

        # Execute revision
        notify_progress(state, f'revision_{round_num}', 'start', f'Applying revisions for round {round_num}...')
        result = revise_report_content(
            state['current_report'],
            verification_dict,
            state['company_data'],
            state['transcript'],
            round_num,
            state['api_config']
        )

        print(f"\n✅ Revision complete!")
        print(f"   ├─ Issues addressed: {result.issues_addressed}")
        print(f"   └─ Suggestions implemented: {result.suggestions_implemented}")
        print(f"🔀 Orchestrator routing to: Verification Agent (Round {round_num + 1})")
        print("="*70)

        # Store revision result
        revision_entry = {
            'round': round_num,
            'issues_addressed': result.issues_addressed,
            'suggestions_implemented': result.suggestions_implemented,
            'revision_notes': result.revision_notes,
            'revision_summary': result.revision_summary
        }

        notify_progress(state, f'revision_{round_num}', 'complete', f'Completed revisions for round {round_num}.')
        return {
            **state,
            'current_report': result.revised_report,
            'report_history': state['report_history'] + [result.revised_report],
            'revision_history': state['revision_history'] + [revision_entry],
            'verification_round': round_num + 1,  # Increment round AFTER revision (matches procedural)
            'status': 'revised'
        }

    except Exception as e:
        print(f"\n❌ ERROR in revision: {str(e)}")
        print("="*70)
        notify_progress(state, f'revision_{round_num}', 'complete', f'Revision failed in round {round_num}.')
        return {
            **state,
            'status': 'error',
            'error_message': f'Revision failed: {str(e)}'
        }


def save_report_node(state: WorkflowState) -> WorkflowState:
    """
    Node 5: Save final report to DOCX.
    Wraps _ensure_report_saved() logic
    """
    print("\n" + "="*70)
    print("💾 NODE 5: SAVE REPORT")
    print("="*70)
    print(f"🤖 Orchestrator saving final report...")

    try:
        from app.formatting.formatter import create_word_doc
        notify_progress(state, 'finalization', 'start', 'Saving final report...')
        # Create safe filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company_name_safe = re.sub(
            r'[^\w\s-]', '',
            state['company_data'].get('company_name', 'Unknown')
        ).strip().replace(' ', '_')

        # Save as DOCX
        doc_path = os.path.join(state['output_dir'], f"{company_name_safe}.docx")
        os.makedirs(state['output_dir'], exist_ok=True)
        create_word_doc(state['current_report'], doc_path, state['company_data'])

        print(f"\n✅ Report saved successfully!")
        print(f"   └─ Path: {doc_path}")
        print("="*70)
        notify_progress(state, 'finalization', 'complete', 'Report finalized.')
        return {
            **state,
            'final_report_content': state['current_report'],
            'final_report_path': doc_path,
            'status': 'completed'
        }

    except Exception as e:
        print(f"\n❌ ERROR saving report: {str(e)}")
        print("="*70)
        notify_progress(state, 'finalization', 'complete', 'Failed to save report.')
        return {
            **state,
            'status': 'error',
            'error_message': f'Save failed: {str(e)}'
        }


# ========================================
# Conditional Edge Functions
# ========================================

def should_continue_after_transcription(state: WorkflowState) -> str:
    """Route after transcription node"""
    if state['status'] == 'error':
        return END
    return "generate_report"


def should_continue_after_report_generation(state: WorkflowState) -> str:
    """Route after report generation node"""
    if state['status'] == 'error':
        return END
    return "verify_report"


def should_continue_after_verification(state: WorkflowState) -> str:
    """
    Route after verification - matches procedural logic exactly.

    Routing Rules (matching procedural workflow):
    1. Error → END
    2. Approved (needs_revision=False) → save_report
    3. Needs revision && within max_rounds → revise_report (even on last round!)

    Key: Procedural increments round AFTER revise, so we revise on rounds 1,2,3
    when max_rounds=3, then the counter becomes 4 and loop exits.
    """
    if state['status'] == 'error':
        return END

    needs_revision = state.get('needs_revision', False)
    current_round = state.get('verification_round', 1)
    max_rounds = state.get('verification_rounds', 5)

    # Approved - no revision needed (matches: if not needs_revision: break)
    if not needs_revision:
        print(f"🎯 Routing: Approved → Save Report")
        return "save_report"

    # Needs revision - check if we can revise (matches: if verification_round <= max_rounds)
    # In procedural, this check happens BEFORE increment, so we check current_round
    if current_round <= max_rounds:
        print(f"🎯 Routing: Needs revision (Round {current_round}/{max_rounds}) → Revise Report")
        return "revise_report"

    # Should never reach here if logic matches procedural, but safety fallback
    print(f"🎯 Routing: Max rounds exceeded ({current_round} > {max_rounds}) → Save Report (convergence)")
    return "save_report"


def should_continue_after_revision(state: WorkflowState) -> str:
    """
    Route after revision - matches procedural loop exit logic.

    Procedural increments AFTER revision, then checks while condition.
    If verification_round > max_rounds after increment, loop exits.
    """
    if state['status'] == 'error':
        return END

    # After revision, round was incremented. Check if we exceeded max_rounds
    current_round = state.get('verification_round', 1)
    max_rounds = state.get('verification_rounds', 5)

    # If we've exceeded max rounds after revision, save (matches procedural loop exit)
    if current_round > max_rounds:
        print(f"🎯 Routing: Loop exit after revision (Round {current_round} > {max_rounds}) → Save Report")
        return "save_report"

    # Otherwise, continue to next verification round
    print(f"🎯 Routing: After revision → Verify Report (Round {current_round})")
    return "verify_report"


# ========================================
# Workflow Graph Builder
# ========================================

def build_workflow_graph():
    """
    Build the LangGraph workflow for V6.

    Graph Structure:
    START → transcribe → generate → verify ⇄ revise → save → END
    """

    # Create state graph
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("transcribe_audio", transcribe_audio_node)
    workflow.add_node("generate_report", generate_report_node)
    workflow.add_node("verify_report", verify_report_node)
    workflow.add_node("revise_report", revise_report_node)
    workflow.add_node("save_report", save_report_node)

    # Set entry point
    workflow.set_entry_point("transcribe_audio")

    # Add conditional edges
    workflow.add_conditional_edges(
        "transcribe_audio",
        should_continue_after_transcription,
        {
            "generate_report": "generate_report",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "generate_report",
        should_continue_after_report_generation,
        {
            "verify_report": "verify_report",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "verify_report",
        should_continue_after_verification,
        {
            "revise_report": "revise_report",
            "save_report": "save_report",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "revise_report",
        should_continue_after_revision,
        {
            "verify_report": "verify_report",
            "save_report": "save_report",
            END: END
        }
    )

    # Save report → END
    workflow.add_edge("save_report", END)

    # Compile and return
    return workflow.compile()


# ========================================
# LangGraphOrchestrator Class
# ========================================

class LangGraphOrchestrator:
    """
    LangGraph-based orchestrator for V6 AI Consultancy Report Generation.
    Drop-in replacement for SDKOrchestrator with identical API.
    """

    def __init__(self, api_config: Dict[str, Any], verification_rounds: int = 5):
        """Initialize LangGraph orchestrator"""
        self.api_config = api_config
        self.verification_rounds = max(1, min(verification_rounds, 5))
        self.workflow = build_workflow_graph()

        print(f"🌟 LANGGRAPH AGENTIC WORKFLOW ORCHESTRATOR INITIALIZED")
        print(f"🔄 Max Verification Rounds: {self.verification_rounds}")
        print(f"🎯 Workflow: Transcription → Generation → Verification ⇄ Revision → Save")

    def process_recording(self, file_path: str, output_dir: str,
                         company_data: Dict[str, Any],
                         meeting_notes: str = "",
                         additional_instructions: str = "",
                         compress_audio: bool = True,
                         progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Process an audio/video recording through LangGraph workflow.

        Args:
            file_path: Path to audio/video file
            output_dir: Directory to save outputs
            company_data: Company information dictionary
            meeting_notes: Additional meeting notes
            additional_instructions: Additional instructions for report
            compress_audio: Whether to compress audio before transcription

        Returns:
            Dict with workflow results (same format as SDKOrchestrator)
        """

        print(f"\n🚀 Starting LangGraph workflow for: {os.path.basename(file_path)}")

        # Initialize state
        initial_state = {
            'audio_file_path': file_path,
            'transcript': None,
            'output_dir': output_dir,
            'company_data': company_data,
            'meeting_notes': meeting_notes,
            'additional_instructions': additional_instructions,
            'compress_audio': compress_audio,
            'api_config': self.api_config,
            'verification_rounds': self.verification_rounds,
            'transcript_path': None,
            'current_report': '',
            'report_history': [],
            'verification_round': 1,
            'verification_history': [],
            'revision_history': [],
            'needs_revision': False,
            'status': 'initialized',
            'error_message': None,
            'last_verification_result': None,
            'final_report_content': '',
            'final_report_path': '',
            'sample_report': None,
            'progress_callback': progress_callback
        }

        try:
            # Execute workflow
            final_state = self.workflow.invoke(initial_state)

            # Format results to match SDKOrchestrator output
            return self._format_workflow_results(final_state)

        except Exception as e:
            print(f"❌ LangGraph workflow failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'company_data': company_data,
                'verification_history': [],
                'revision_history': [],
                'final_report': None
            }

    def process_transcript(self, transcript: str, output_dir: str,
                          company_data: Dict[str, Any],
                          meeting_notes: str = "",
                          additional_instructions: str = "",
                          progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """
        Process existing transcript through LangGraph workflow.

        Args:
            transcript: Existing transcript text
            output_dir: Directory to save outputs
            company_data: Company information dictionary
            meeting_notes: Additional meeting notes
            additional_instructions: Additional instructions for report

        Returns:
            Dict with workflow results (same format as SDKOrchestrator)
        """

        print(f"\n🚀 Starting LangGraph workflow with existing transcript")

        # Initialize state (no audio file, use provided transcript)
        initial_state = {
            'audio_file_path': None,  # No audio file
            'transcript': transcript,  # Use provided transcript
            'output_dir': output_dir,
            'company_data': company_data,
            'meeting_notes': meeting_notes,
            'additional_instructions': additional_instructions,
            'compress_audio': True,  # N/A
            'api_config': self.api_config,
            'verification_rounds': self.verification_rounds,
            'transcript_path': None,
            'current_report': '',
            'report_history': [],
            'verification_round': 1,
            'verification_history': [],
            'revision_history': [],
            'needs_revision': False,
            'status': 'transcription_skipped',  # Skip transcription
            'error_message': None,
            'last_verification_result': None,
            'final_report_content': '',
            'final_report_path': '',
            'sample_report': None,
            'progress_callback': progress_callback
        }

        try:
            # Execute workflow
            final_state = self.workflow.invoke(initial_state)

            # Format results to match SDKOrchestrator output
            return self._format_workflow_results(final_state)

        except Exception as e:
            print(f"❌ LangGraph workflow failed: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'company_data': company_data,
                'verification_history': [],
                'revision_history': [],
                'final_report': None
            }

    def _format_workflow_results(self, final_state: WorkflowState) -> Dict[str, Any]:
        """Format LangGraph state into SDKOrchestrator-compatible results"""

        if final_state['status'] == 'error':
            return {
                'status': 'failed',
                'error': final_state.get('error_message', 'Unknown error'),
                'company_data': final_state['company_data'],
                'verification_history': final_state['verification_history'],
                'revision_history': final_state['revision_history'],
                'final_report': None,
                'transcript_path': final_state.get('transcript_path')
            }

        # Success case - format results
        results = {
            'status': 'success',
            'company_data': final_state['company_data'],
            'verification_history': final_state['verification_history'],
            'revision_history': final_state['revision_history'],
            'final_report': {
                'content': final_state['final_report_content'],
                'doc_path': final_state['final_report_path']
            },
            'final_report_content': final_state['final_report_content'],
            'final_report_path': final_state['final_report_path'],
            'transcript_path': final_state.get('transcript_path')
        }

        # Add individual verification results for compatibility
        for i, ver_result in enumerate(final_state['verification_history'], 1):
            results[f'verification_{i}_results'] = ver_result

        # Add individual revision results for compatibility
        for i, rev_result in enumerate(final_state['revision_history'], 1):
            results[f'revision_{i}_results'] = rev_result

        print(f"\n✅ LANGGRAPH WORKFLOW COMPLETED SUCCESSFULLY!")
        print(f"📊 Final Score: {final_state['verification_history'][-1]['score']}/10")
        print(f"🔄 Total Rounds: {len(final_state['verification_history'])}")

        return results


def create_langgraph_orchestrator(api_config: Dict[str, Any],
                                  verification_rounds: int = 5) -> LangGraphOrchestrator:
    """
    Factory function to create LangGraph orchestrator.

    Args:
        api_config: API configuration dictionary
        verification_rounds: Number of verification rounds (1-5)

    Returns:
        LangGraphOrchestrator: Configured LangGraph orchestrator instance
    """
    return LangGraphOrchestrator(api_config, verification_rounds)
