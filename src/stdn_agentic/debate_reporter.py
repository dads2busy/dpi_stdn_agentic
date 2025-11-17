"""
Debate reporting and transcript generation for STDN

This module provides tools for generating, formatting, and saving debate
transcripts from multi-agent consensus-building processes.

For government/policy work, transparent decision-making is critical. The
DebateReporter creates:
- Human-readable debate transcripts
- Machine-readable JSON exports
- Policy-ready formatted briefs
- Audit trails with timestamps and reasoning
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class DebateReporter:
    """
    Generate and save debate transcripts for audit and analysis.

    Provides multiple output formats:
    - Text transcripts for human review
    - JSON exports for programmatic analysis
    - Policy briefs for decision-makers

    Attributes:
        output_dir: Directory where transcripts are saved

    Example:
        >>> reporter = DebateReporter(output_dir="./debate_transcripts")
        >>> filepath = reporter.save_debate_transcript(
        ...     technology="smartphone",
        ...     agent_responses=agent_data,
        ...     debate_rounds=rounds,
        ...     final_consensus=consensus
        ... )
    """

    def __init__(self, output_dir: str = "./debate_transcripts"):
        """
        Initialize the debate reporter.

        Args:
            output_dir: Directory to save transcripts (created if doesn't exist)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_debate_transcript(
        self,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
        file_format: str = "txt",
    ) -> Path:
        """
        Save debate transcript to file.

        Args:
            technology: Technology being debated
            agent_responses: List of initial agent proposals
            debate_history: List of debate round results with convergence
            final_consensus: Final consensus data
            file_format: Output format ('txt' or 'json')

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{technology.replace(' ', '_')}_{timestamp}.{file_format}"
        filepath = self.output_dir / filename

        if file_format == "json":
            self._save_json_transcript(
                filepath, technology, agent_responses, debate_history, final_consensus
            )
        else:
            self._save_text_transcript(
                filepath, technology, agent_responses, debate_history, final_consensus
            )

        return filepath

    def _save_text_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as formatted text file"""
        with open(filepath, "w") as f:
            # Header
            f.write("=" * 80 + "\n")
            f.write(f"MULTI-AGENT DEBATE TRANSCRIPT: {technology}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

            # Phase 1: Initial Proposals
            f.write("PHASE 1: INDEPENDENT COMPONENT EXTRACTION\n")
            f.write("-" * 80 + "\n\n")

            for idx, round_data in enumerate(agent_responses):
                agent_id = round_data.get("agent_id", f"Agent_{idx + 1}")
                components = round_data.get("components", [])

                f.write(f"{agent_id}:\n")
                f.write(f"  Role: {round_data.get('persona', 'Unknown')}\n")
                f.write(f"  Proposed Components ({len(components)}):\n")

                for comp in components:
                    if isinstance(comp, dict):
                        name = comp.get("name", comp.get("component", comp))
                        confidence = comp.get("confidence", "N/A")
                        reasoning = comp.get("reasoning", "")
                        f.write(f"    - {name} (confidence: {confidence})\n")
                        if reasoning:
                            f.write(f"      Reasoning: {reasoning}\n")
                    else:
                        f.write(f"    - {comp}\n")
                f.write("\n")

            # Phase 2: Debate Rounds (NEW - was missing!)
            if debate_history:
                f.write("\n" + "=" * 80 + "\n")
                f.write("PHASE 2: DEBATE ROUNDS\n")
                f.write("=" * 80 + "\n\n")

                for round_data in debate_history:
                    round_num = round_data.get("round_num", 0)
                    convergence = round_data.get("convergence", 0.0)

                    f.write(f"ROUND {round_num}:\n")
                    f.write(f"  Convergence: {convergence:.1%}\n")
                    f.write(
                        f"  Status: {'✓ Threshold reached' if convergence >= 0.51 else '→ Continuing debate'}\n"
                    )
                    f.write("\n")

            # Phase 3: Final Consensus
            f.write("\n" + "=" * 80 + "\n")
            f.write("PHASE 3: FINAL CONSENSUS\n")
            f.write("=" * 80 + "\n\n")

            if isinstance(final_consensus, dict):
                consensus_comps = final_consensus.get("components", [])
                num_rounds = final_consensus.get("rounds", 0)
                confidence = final_consensus.get("confidence", 0.0)
            else:
                consensus_comps = final_consensus if isinstance(final_consensus, list) else []
                num_rounds = 0
                confidence = 0.0

            f.write(f"Total Debate Rounds: {num_rounds}\n")
            f.write(f"Overall Consensus Confidence: {confidence:.2f}\n\n")
            f.write(f"Final Consensus Components ({len(consensus_comps)}):\n")

            for comp in consensus_comps:
                if isinstance(comp, dict):
                    name = comp.get("name", comp.get("component", comp))
                    comp_confidence = comp.get("confidence", "N/A")
                    f.write(f"  ✓ {name} (confidence: {comp_confidence})\n")
                else:
                    f.write(f"  ✓ {comp}\n")

            # Footer
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF DEBATE TRANSCRIPT\n")
            f.write("=" * 80 + "\n")

    def _save_json_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as JSON file"""
        transcript = {
            "technology": technology,
            "timestamp": datetime.now().isoformat(),
            "phase1_initial_proposals": agent_responses,
            "phase2_debate_rounds": debate_history,
            "phase3_final_consensus": final_consensus,
        }

        with open(filepath, "w") as f:
            json.dump(transcript, f, indent=2, default=str)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "DebateReporter",
]
