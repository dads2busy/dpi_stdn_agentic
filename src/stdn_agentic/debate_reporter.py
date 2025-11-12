"""
Debate transcript reporter

Generates and saves formatted debate transcripts in multiple formats:
- Text (human-readable)
- JSON (structured data)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class DebateReporter:
    """Generate and save debate transcripts"""

    def __init__(self, output_dir: str = "./debate_transcripts"):
        """
        Initialize reporter

        Args:
            output_dir: Directory to save transcripts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_debate_transcript(
        self,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_rounds: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
        file_format: str = "txt",
    ) -> Path:
        """
        Save debate transcript to file

        Args:
            technology: Technology being debated
            agent_responses: List of initial agent proposals
            debate_rounds: List of debate round results
            final_consensus: Final consensus data
            file_format: Output format ("txt" or "json")

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{technology.replace(' ', '_')}_{timestamp}.{file_format}"
        filepath = self.output_dir / filename

        if file_format == "json":
            self._save_json_transcript(
                filepath, technology, agent_responses, debate_rounds, final_consensus
            )
        else:
            self._save_text_transcript(
                filepath, technology, agent_responses, debate_rounds, final_consensus
            )

        return filepath

    def _save_text_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_rounds: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as formatted text file"""
        with open(filepath, "w") as f:
            f.write("=" * 80 + "\n")
            f.write(f"MULTI-AGENT DEBATE TRANSCRIPT: {technology}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

            # PHASE 1: Initial proposals
            f.write("PHASE 1: INDEPENDENT COMPONENT EXTRACTION\n")
            f.write("-" * 80 + "\n\n")

            for round_idx, round_data in enumerate(agent_responses):
                agent_id = round_data.get("agent_id", f"Agent {round_idx + 1}")
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

            # PHASE 2: Debate rounds
            if debate_rounds:
                f.write("\n" + "=" * 80 + "\n")
                f.write("PHASE 2: DEBATE AND CRITIQUE\n")
                f.write("=" * 80 + "\n\n")

                for round_idx, round_data in enumerate(debate_rounds, 1):
                    convergence = round_data.get("convergence_score", 0.0)

                    f.write(f"DEBATE ROUND {round_idx}\n")
                    f.write(f"Convergence Score: {convergence:.1%}\n")
                    f.write("-" * 80 + "\n\n")

                    responses = round_data.get("agent_responses", [])
                    for response in responses:
                        agent_id = response.get("agent_id", "Unknown Agent")
                        components = response.get("components", [])
                        critique = response.get("critique_of_others", "")

                        f.write(f"{agent_id} Response:\n")
                        f.write(f"  Components:\n")

                        for comp in components:
                            if isinstance(comp, dict):
                                name = comp.get("name", comp.get("component", comp))
                                confidence = comp.get("confidence", "N/A")
                                f.write(f"    - {name} (confidence: {confidence})\n")
                            else:
                                f.write(f"    - {comp}\n")

                        if critique:
                            f.write(f"\n  Critique:\n")
                            for line in critique.split("\n"):
                                if line.strip():
                                    f.write(f"    {line}\n")
                        f.write("\n")

            # PHASE 3: Final consensus
            f.write("\n" + "=" * 80 + "\n")
            f.write("PHASE 3: FINAL CONSENSUS\n")
            f.write("=" * 80 + "\n\n")

            if isinstance(final_consensus, dict):
                consensus_comps = final_consensus.get("components", [])
                summary = final_consensus.get("debate_summary", "")
                num_rounds = final_consensus.get("num_rounds", 0)
                confidence = final_consensus.get("confidence", 0.0)
            else:
                consensus_comps = final_consensus if isinstance(final_consensus, list) else []
                summary = ""
                num_rounds = 0
                confidence = 0.0

            f.write(f"Total Debate Rounds: {num_rounds}\n")
            f.write(f"Overall Consensus Confidence: {confidence:.2f}\n")
            f.write(f"\nFinal Consensus Components ({len(consensus_comps)}):\n")

            for comp in consensus_comps:
                if isinstance(comp, dict):
                    name = comp.get("name", comp.get("component", comp))
                    comp_confidence = comp.get("confidence", "N/A")
                    f.write(f"  ✓ {name} (confidence: {comp_confidence})\n")
                else:
                    f.write(f"  ✓ {comp}\n")

            if summary:
                f.write(f"\nDebate Summary:\n")
                for line in summary.split("\n"):
                    if line.strip():
                        f.write(f"  {line}\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF DEBATE TRANSCRIPT\n")
            f.write("=" * 80 + "\n")

    def _save_json_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_rounds: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as JSON file"""
        transcript = {
            "technology": technology,
            "timestamp": datetime.now().isoformat(),
            "phase_1_initial_proposals": agent_responses,
            "phase_2_debate_rounds": debate_rounds,
            "phase_3_final_consensus": final_consensus,
        }

        with open(filepath, "w") as f:
            json.dump(transcript, f, indent=2, default=str)
