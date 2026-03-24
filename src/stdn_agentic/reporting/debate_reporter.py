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

from .transcript_models import (
    TRANSCRIPT_WIDTH,
)


class DebateReporter:
    """
    Generate and save debate transcripts for audit and analysis.

    Provides multiple output formats:
    - Text transcripts for human review
    - JSON exports for programmatic analysis
    - Policy briefs for decision-makers

    Attributes:
        output_dir: Directory where transcripts are saved
    """

    def __init__(self, output_dir: str = "./output/transcripts"):
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
        timestamp: str | None = None,
        config_tag: str | None = None,
    ) -> Path:
        """
        Save debate transcript to file.

        Args:
            technology: Technology being debated
            agent_responses: List of initial agent proposals
            debate_history: List of debate round results with convergence
            final_consensus: Final consensus data
            file_format: Output format ('txt' or 'json')
            timestamp: Optional timestamp string (YYYYMMDD_HHMMSS), generates new if None

        Returns:
            Path to saved file
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tech_part = technology.replace("/", "-").replace(" ", "_")
        if config_tag:
            filename = f"{tech_part}_{config_tag}_{timestamp}.{file_format}"
        else:
            filename = f"{tech_part}_{timestamp}.{file_format}"

        filepath = self.output_dir / filename

        if file_format == "json":
            self._save_json_transcript(
                filepath, technology, agent_responses, debate_history, final_consensus
            )
        else:
            self._save_text_transcript_v2(
                filepath, technology, agent_responses, debate_history, final_consensus
            )

        return filepath

    def _save_text_transcript_v2(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as formatted text file (new improved format)."""
        with open(filepath, "w") as f:
            # ===== HEADER =====
            f.write("=" * TRANSCRIPT_WIDTH + "\n")
            f.write(f"STDN ANALYSIS: {technology}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

            # ===== LEGEND =====
            f.write("\nLEGEND\n")
            f.write("-" * TRANSCRIPT_WIDTH + "\n")
            f.write("Support Levels:\n")
            f.write("  [C] CONSENSUS  - All agents agree (3/3)\n")
            f.write("  [M] MAJORITY   - Majority agrees (2/3)\n")
            f.write("  [I] ISOLATED   - Single agent only (1/3)\n")
            f.write("\nConfidence Scale: 0.0-1.0 (higher = more certain)\n")
            f.write("  0.9-1.0: High certainty - universal/essential\n")
            f.write("  0.7-0.9: Confident - industry standard\n")
            f.write("  0.5-0.7: Moderate - common but varies\n")
            f.write("  <0.5:    Low - optional or uncertain\n")

            # ===== TECHNOLOGY SPECIFICATION =====
            tech_spec = final_consensus.get("technology_specification", technology)
            tech_reasoning = final_consensus.get("technology_reasoning", "")

            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("TECHNOLOGY SPECIFICATION\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n\n")
            f.write(f"Query: {technology}\n")
            f.write(f"Specification: {tech_spec}\n")
            if tech_reasoning:
                f.write(f"\nReasoning: {tech_reasoning}\n")

            # ===== STAGE 1: COMPONENT EXTRACTION =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("STAGE 1: COMPONENT EXTRACTION\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

            # Get number of agents
            num_agents = len(agent_responses) if agent_responses else 3

            # Round 1: Initial Proposals
            f.write("\nROUND 1: Independent Proposals\n")
            f.write("-" * TRANSCRIPT_WIDTH + "\n")

            for idx, response in enumerate(agent_responses):
                agent_id = response.get("agent_id", f"Agent_{idx + 1}")
                role = response.get("persona", response.get("role", "Expert"))
                components = response.get("components", [])

                f.write(f"\n{agent_id} ({role}):\n")
                for comp in components:
                    if isinstance(comp, dict):
                        name = comp.get("name", comp.get("component", str(comp)))
                        confidence = comp.get("confidence", 0.0)
                        reasoning = comp.get("reasoning", "")
                        f.write(f"  • {name} ({confidence:.2f})")
                        if reasoning:
                            # Truncate long reasoning
                            short_reason = (
                                reasoning[:60] + "..." if len(reasoning) > 60 else reasoning
                            )
                            f.write(f" - {short_reason}")
                        f.write("\n")
                    else:
                        f.write(f"  • {comp}\n")

            # Compute initial support analysis
            if agent_responses:
                initial_support = self._compute_support_analysis(agent_responses, num_agents)
                f.write(self._format_support_analysis(initial_support, num_agents, "Initial"))

            # Subsequent rounds
            if debate_history:
                for round_data in debate_history:
                    round_num = round_data.get("round_num", 0)
                    convergence = round_data.get("convergence", 0.0)
                    proposals = round_data.get("proposals", {})

                    # Skip round 1 as we already showed initial proposals
                    if round_num <= 1:
                        continue

                    # Use enhanced data if available, otherwise fall back to defaults
                    threshold = round_data.get("threshold", 0.75)
                    threshold_reached = round_data.get(
                        "threshold_reached", convergence >= threshold
                    )

                    f.write(
                        f"\nROUND {round_num}: {'Consensus Reached' if threshold_reached else 'Refinement'}\n"
                    )
                    f.write("-" * TRANSCRIPT_WIDTH + "\n")
                    f.write(f"Convergence: {convergence:.1%}")
                    if threshold_reached:
                        f.write(" ✓ (threshold reached)\n")
                    else:
                        f.write(f" (threshold: {threshold:.0%})\n")

                    # Show changes from previous round if available
                    changes = round_data.get("changes_from_previous")
                    if changes:
                        added = changes.get("items_added", [])
                        removed = changes.get("items_removed", [])
                        conf_changes = changes.get("confidence_changes", {})

                        if added or removed or conf_changes:
                            f.write("\nChanges from Previous Round:\n")
                            if added:
                                f.write(f"  + Added: {', '.join(added[:5])}")
                                if len(added) > 5:
                                    f.write(f" (+{len(added) - 5} more)")
                                f.write("\n")
                            if removed:
                                f.write(f"  - Removed: {', '.join(removed[:5])}")
                                if len(removed) > 5:
                                    f.write(f" (+{len(removed) - 5} more)")
                                f.write("\n")
                            if conf_changes:
                                f.write(f"  ~ Confidence changes: {len(conf_changes)} items\n")

                    # Show structured critiques if available (new format)
                    structured_critiques = round_data.get("critiques", [])
                    if structured_critiques and isinstance(structured_critiques, list):
                        # Check if it's the new structured format
                        if structured_critiques and isinstance(structured_critiques[0], dict):
                            f.write("\nKey Critiques:\n")
                            # Group by support level for cleaner output
                            consensus_critiques = [
                                c
                                for c in structured_critiques
                                if c.get("support_level") == "consensus"
                            ]
                            isolated_critiques = [
                                c
                                for c in structured_critiques
                                if c.get("support_level") == "isolated"
                            ]

                            # Show consensus items (abbreviated)
                            if consensus_critiques:
                                f.write(
                                    f"  [C] {len(consensus_critiques)} items have full consensus\n"
                                )

                            # Show isolated items (these need attention)
                            for critique in isolated_critiques[:3]:
                                item_name = critique.get("item_name", "Unknown")
                                avg_conf = critique.get("avg_confidence", 0.0)
                                f.write(
                                    f"  [I] {item_name} (conf: {avg_conf:.2f}) - needs peer support\n"
                                )

                            if len(isolated_critiques) > 3:
                                f.write(
                                    f"      ... and {len(isolated_critiques) - 3} more isolated items\n"
                                )
                        else:
                            # Legacy format - show as before
                            f.write("\nCritiques:\n")
                            for critique in structured_critiques[:5]:
                                if isinstance(critique, dict):
                                    f.write(f"  {critique.get('critique_text', str(critique))}\n")
                                else:
                                    f.write(f"  {critique}\n")

                    # Use enhanced support analysis if available
                    support_analysis = round_data.get("support_analysis")
                    if support_analysis:
                        f.write(
                            self._format_enhanced_support_analysis(
                                support_analysis, num_agents, f"Round {round_num}"
                            )
                        )
                    elif proposals:
                        # Fall back to computing from proposals
                        round_support = self._compute_support_from_proposals(proposals, num_agents)
                        f.write(
                            self._format_support_analysis(
                                round_support, num_agents, f"Round {round_num}"
                            )
                        )

            # ===== FINAL CONSENSUS =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("FINAL CONSENSUS: Components\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n\n")

            if isinstance(final_consensus, dict):
                consensus_comps = final_consensus.get("components", [])
                num_rounds = final_consensus.get(
                    "rounds", len(debate_history) if debate_history else 1
                )
                overall_confidence = final_consensus.get("confidence", 0.0)
            else:
                consensus_comps = final_consensus if isinstance(final_consensus, list) else []
                num_rounds = 1
                overall_confidence = 0.0

            f.write(f"Rounds Completed: {num_rounds}\n")
            f.write(f"Final Convergence: {overall_confidence:.1%}\n")
            f.write(f"Components Selected: {len(consensus_comps)}\n\n")

            for i, comp in enumerate(consensus_comps, 1):
                if isinstance(comp, dict):
                    name = comp.get("name", comp.get("component", str(comp)))
                    confidence = comp.get("confidence", 0.0)
                    f.write(f"  {i}. {name} ({confidence:.2f})\n")
                else:
                    f.write(f"  {i}. {comp}\n")

            # ===== FOOTER =====
            f.write("\n" + "=" * TRANSCRIPT_WIDTH + "\n")
            f.write("END OF COMPONENT EXTRACTION\n")
            f.write("=" * TRANSCRIPT_WIDTH + "\n")

    def _compute_support_analysis(
        self, agent_responses: List[Dict[str, Any]], num_agents: int
    ) -> Dict[str, Dict]:
        """Compute support levels for components across agents."""
        component_support = {}

        for response in agent_responses:
            agent_id = response.get("agent_id", "Unknown")
            components = response.get("components", [])

            for comp in components:
                if isinstance(comp, dict):
                    name = comp.get("name", comp.get("component", str(comp))).lower()
                    confidence = comp.get("confidence", 0.0)
                else:
                    name = str(comp).lower()
                    confidence = 0.5

                if name not in component_support:
                    component_support[name] = {
                        "display_name": comp.get("name", str(comp))
                        if isinstance(comp, dict)
                        else str(comp),
                        "agents": [],
                        "confidences": [],
                    }
                component_support[name]["agents"].append(agent_id)
                component_support[name]["confidences"].append(confidence)

        return component_support

    def _compute_support_from_proposals(
        self, proposals: Dict[str, List], num_agents: int
    ) -> Dict[str, Dict]:
        """Compute support levels from round proposals."""
        component_support = {}

        for agent_id, items in proposals.items():
            for item in items:
                if isinstance(item, dict):
                    name = item.get("component", item.get("name", str(item))).lower()
                    confidence = item.get("confidence", 0.0)
                    display_name = item.get("component", item.get("name", str(item)))
                else:
                    name = str(item).lower()
                    confidence = 0.5
                    display_name = str(item)

                if name not in component_support:
                    component_support[name] = {
                        "display_name": display_name,
                        "agents": [],
                        "confidences": [],
                    }
                component_support[name]["agents"].append(agent_id)
                component_support[name]["confidences"].append(confidence)

        return component_support

    def _format_support_analysis(
        self, support: Dict[str, Dict], num_agents: int, label: str
    ) -> str:
        """Format support analysis as readable text."""
        lines = [f"\n{label} Support Analysis:\n"]

        consensus = []
        majority = []
        isolated = []

        for _name, data in support.items():
            count = len(data["agents"])
            avg_conf = (
                sum(data["confidences"]) / len(data["confidences"]) if data["confidences"] else 0
            )
            display = data["display_name"]

            if count == num_agents:
                consensus.append((display, avg_conf, count))
            elif count > num_agents / 2:
                majority.append((display, avg_conf, count))
            else:
                isolated.append((display, avg_conf, count))

        if consensus:
            lines.append(f"  [C] Consensus ({len(consensus)} items):\n")
            for display, conf, _count in sorted(consensus, key=lambda x: -x[1])[:5]:
                lines.append(f"      • {display} ({conf:.2f})\n")

        if majority:
            lines.append(f"  [M] Majority ({len(majority)} items):\n")
            for display, conf, count in sorted(majority, key=lambda x: -x[1])[:5]:
                lines.append(f"      • {display} ({conf:.2f}) - {count}/{num_agents} agents\n")

        if isolated:
            lines.append(f"  [I] Isolated ({len(isolated)} items):\n")
            for display, conf, _count in sorted(isolated, key=lambda x: -x[1])[:3]:
                lines.append(f"      • {display} ({conf:.2f}) - needs peer support\n")

        return "".join(lines)

    def _format_enhanced_support_analysis(
        self, support_analysis: Dict[str, Any], num_agents: int, label: str
    ) -> str:
        """Format enhanced support analysis from debate code (new format)."""
        lines = [f"\n{label} Support Analysis:\n"]

        consensus = support_analysis.get("consensus", [])
        majority = support_analysis.get("majority", [])
        isolated = support_analysis.get("isolated", [])

        if consensus:
            lines.append(f"  [C] Consensus ({len(consensus)} items):\n")
            for item in consensus[:5]:
                lines.append(f"      • {item}\n")
            if len(consensus) > 5:
                lines.append(f"      ... and {len(consensus) - 5} more\n")

        if majority:
            lines.append(f"  [M] Majority ({len(majority)} items):\n")
            for item in majority[:5]:
                lines.append(f"      • {item} - partial agreement\n")
            if len(majority) > 5:
                lines.append(f"      ... and {len(majority) - 5} more\n")

        if isolated:
            lines.append(f"  [I] Isolated ({len(isolated)} items):\n")
            for item in isolated[:3]:
                lines.append(f"      • {item} - needs peer support\n")
            if len(isolated) > 3:
                lines.append(f"      ... and {len(isolated) - 3} more\n")

        return "".join(lines)

    def _save_json_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as JSON file with enhanced schema."""
        # Extract tech spec info
        tech_spec = technology
        tech_reasoning = ""

        if agent_responses and len(agent_responses) > 0:
            first_response = agent_responses[0]
            tech_spec = first_response.get("technology_specification", technology)
            tech_reasoning = first_response.get("technology_reasoning", "")

        if isinstance(final_consensus, dict):
            tech_spec = final_consensus.get("technology_specification", tech_spec)
            tech_reasoning = final_consensus.get("technology_reasoning", tech_reasoning)

        transcript = {
            "version": "2.0",
            "metadata": {
                "technology": technology,
                "technology_specification": tech_spec,
                "technology_reasoning": tech_reasoning,
                "timestamp": datetime.now().isoformat(),
                "format_version": "2.0",
            },
            "config": {
                "num_agents": len(agent_responses) if agent_responses else 3,
                "max_rounds": len(debate_history) if debate_history else 3,
            },
            "component_stage": {
                "phase1_initial_proposals": agent_responses,
                "phase2_debate_rounds": debate_history,
                "phase3_final_consensus": final_consensus,
            },
        }

        with open(filepath, "w") as f:
            json.dump(transcript, f, indent=2, default=str)

    # Legacy method for backwards compatibility
    def _save_text_transcript(
        self,
        filepath: Path,
        technology: str,
        agent_responses: List[Dict[str, Any]],
        debate_history: List[Dict[str, Any]],
        final_consensus: Dict[str, Any],
    ):
        """Save debate as formatted text file (legacy format)."""
        # Redirect to new format
        self._save_text_transcript_v2(
            filepath, technology, agent_responses, debate_history, final_consensus
        )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "DebateReporter",
]
