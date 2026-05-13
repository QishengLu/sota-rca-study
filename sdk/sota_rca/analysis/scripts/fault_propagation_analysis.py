"""
RCABench Dataset Analysis - Simplified Fault Propagation Analysis

This script provides two modes:

1. Standard Analysis Mode (default):
   - Fault Type × Service heatmap - shows which fault types affect which services
   - Service Dependency Graph - shows fault propagation paths with edge thickness indicating frequency

2. Diverse Case Selection Mode (--select-diverse):
   - Selects diverse cases to maximize coverage of (fault_type, service) pairs
   - Uses greedy algorithm to ensure diversity
   - Supports service suppression to limit cases for specific services
   - Outputs selected case names to a file
   - Generates heatmap and coverage comparison visualizations

Usage:
    # Standard analysis
    python fault_propagation_analysis.py --dataset-path data/rcabench_dataset

    # Diverse case selection
    python fault_propagation_analysis.py --dataset-path data/rcabench_dataset --select-diverse --target-count 100

    # Diverse case selection with service suppression
    python fault_propagation_analysis.py --dataset-path data/rcabench_dataset --select-diverse --target-count 100 \
        --suppress-service ts-ui-dashboard:5 --suppress-service mysql:10
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns
from tqdm import tqdm


class FaultPropagationAnalyzer:
    """Analyzer for fault type distribution and service-level propagation."""

    def __init__(self, dataset_path: str | Path):
        """Initialize the analyzer.

        Args:
            dataset_path: Path to the RCABench dataset directory
        """
        self.dataset_path = Path(dataset_path)

    def find_valid_cases(self) -> list[Path]:
        """Find all valid cases with causal_graph.json."""
        valid_cases = []
        for case_dir in self.dataset_path.iterdir():
            if not case_dir.is_dir():
                continue

            causal_graph_file = case_dir / "converted" / "causal_graph.json"
            if causal_graph_file.exists():
                valid_cases.append(case_dir)

        return sorted(valid_cases)

    # Fault type mapping from injection.json fault_type (int) to name
    # Based on InjectionConf struct field order
    FAULT_TYPE_MAP = {
        0: "pod-kill",
        1: "pod-failure",
        2: "container-kill",
        3: "memory-stress",
        4: "cpu-stress",
        5: "http-request-abort",
        6: "http-response-abort",
        7: "http-request-delay",
        8: "http-response-delay",
        9: "http-response-replace-body",
        10: "http-response-patch-body",
        11: "http-request-replace-path",
        12: "http-request-replace-method",
        13: "http-response-replace-code",
        14: "dns-error",
        15: "dns-random",
        16: "time-skew",
        17: "network-delay",
        18: "network-loss",
        19: "network-duplicate",
        20: "network-corrupt",
        21: "network-bandwidth",
        22: "network-partition",
        23: "jvm-latency",
        24: "jvm-return",
        25: "jvm-exception",
        26: "jvm-gc",
        27: "jvm-cpu-stress",
        28: "jvm-memory-stress",
        29: "jvm-mysql-latency",
        30: "jvm-mysql-exception",
    }

    def load_injection_info(self, case_path: Path) -> dict[str, Any]:
        """Load fault type and service from injection.json.

        Args:
            case_path: Path to case directory

        Returns:
            Dictionary with fault_type and services
        """
        injection_file = case_path / "injection.json"
        if not injection_file.exists():
            return {"fault_type": "unknown", "services": ["unknown"]}

        try:
            with open(injection_file) as f:
                data = json.load(f)

            # Get fault type
            fault_type_id = data.get("fault_type")
            if isinstance(fault_type_id, int):
                fault_type = self.FAULT_TYPE_MAP.get(fault_type_id, f"unknown-{fault_type_id}")
            else:
                # Some cases have string fault_type (e.g., "PodFailure")
                fault_type = str(fault_type_id).lower() if fault_type_id else "unknown"

            # Get services from ground_truth
            services = data.get("ground_truth", {}).get("service", [])
            if not services:
                services = ["unknown"]

            return {"fault_type": fault_type, "services": services}

        except Exception:
            return {"fault_type": "unknown", "services": ["unknown"]}

    def extract_service_edges(self, causal_data: dict[str, Any]) -> list[tuple[str, str]]:
        """Extract service-level edges from causal graph.

        Args:
            causal_data: Causal graph data

        Returns:
            List of (source_service, target_service) tuples
        """
        edges = causal_data.get("edges", [])
        component_to_service = causal_data.get("component_to_service", {})

        service_edges = []
        for edge in edges:
            source_component = edge.get("source", "")
            target_component = edge.get("target", "")

            source_service = component_to_service.get(source_component, "unknown")
            target_service = component_to_service.get(target_component, "unknown")

            # Only keep valid cross-service edges
            if source_service != "unknown" and target_service != "unknown" and source_service != target_service:
                service_edges.append((source_service, target_service))

        return service_edges

    def analyze_all_cases(self) -> tuple[pd.DataFrame, Counter]:
        """Analyze all cases for fault-service distribution and service edges.

        Returns:
            Tuple of (fault_service_df, service_edge_counter)
        """
        valid_cases = self.find_valid_cases()
        print(f"Found {len(valid_cases)} valid cases")

        fault_service_records = []
        all_service_edges = []

        for case_path in tqdm(valid_cases, desc="Analyzing cases"):
            case_name = case_path.name

            # Load causal graph
            causal_graph_file = case_path / "converted" / "causal_graph.json"
            try:
                with open(causal_graph_file) as f:
                    causal_data = json.load(f)
            except Exception as e:
                print(f"Error loading {case_name}: {e}")
                continue

            # Load injection info
            injection_info = self.load_injection_info(case_path)

            # Extract service edges for dependency graph
            service_edges = self.extract_service_edges(causal_data)
            all_service_edges.extend(service_edges)

            # Record fault-service tuples
            for service in injection_info["services"]:
                fault_service_records.append(
                    {
                        "fault_type": injection_info["fault_type"],
                        "service": service,
                    }
                )

        # Create DataFrame for fault-service distribution
        df = pd.DataFrame(fault_service_records)

        # Count service edge frequencies
        edge_counter = Counter(all_service_edges)

        return df, edge_counter

    def collect_case_metadata(self) -> list[dict[str, Any]]:
        """Collect metadata for all valid cases including fault_type and services.

        Returns:
            List of dictionaries with case_name, fault_type, and services
        """
        valid_cases = self.find_valid_cases()
        print(f"Found {len(valid_cases)} valid cases")

        case_metadata = []
        for case_path in tqdm(valid_cases, desc="Collecting case metadata"):
            case_name = case_path.name

            # Load injection info
            injection_info = self.load_injection_info(case_path)

            case_metadata.append(
                {
                    "case_name": case_name,
                    "fault_type": injection_info["fault_type"],
                    "services": injection_info["services"],
                }
            )

        return case_metadata

    def select_diverse_cases(
        self,
        case_metadata: list[dict[str, Any]],
        target_count: int | None = None,
        suppressed_services: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Select diverse cases to maximize coverage of (fault_type, service) pairs.

        Uses a greedy algorithm to select cases that cover the most unique pairs.

        Args:
            case_metadata: List of case metadata dictionaries
            target_count: Target number of cases to select (default: auto-determine)
            suppressed_services: Dict mapping service names to max count limits.
                                 e.g., {"ts-ui-dashboard": 5} limits that service to 5 cases.

        Returns:
            List of selected case metadata dictionaries
        """
        if suppressed_services is None:
            suppressed_services = {}

        # Build a mapping of (fault_type, service) -> list of cases
        pair_to_cases = {}
        for case in case_metadata:
            fault_type = case["fault_type"]
            for service in case["services"]:
                pair = (fault_type, service)
                if pair not in pair_to_cases:
                    pair_to_cases[pair] = []
                pair_to_cases[pair].append(case)

        total_pairs = len(pair_to_cases)
        print(f"\nTotal unique (fault_type, service) pairs: {total_pairs}")

        if suppressed_services:
            print(f"Suppressed services: {suppressed_services}")

        # If target_count not specified, aim for ~80% coverage with reasonable sample size
        if target_count is None:
            target_count = min(len(case_metadata), max(50, int(total_pairs * 1.2)))

        print(f"Target case count: {target_count}")

        # Track count per suppressed service
        service_counts = dict.fromkeys(suppressed_services, 0)

        # Greedy selection: prioritize cases that cover uncovered pairs
        selected_cases = []
        covered_pairs = set()
        remaining_cases = case_metadata.copy()

        while len(selected_cases) < target_count and remaining_cases:
            # Score each remaining case by how many new pairs it covers
            best_case = None
            best_score = -1
            best_new_pairs = set()

            for case in remaining_cases:
                # Check if any suppressed service has reached its limit
                skip_case = False
                for service in case["services"]:
                    if service in suppressed_services:
                        if service_counts[service] >= suppressed_services[service]:
                            skip_case = True
                            break

                if skip_case:
                    continue

                case_pairs = {(case["fault_type"], svc) for svc in case["services"]}
                new_pairs = case_pairs - covered_pairs
                score = len(new_pairs)

                # Tie-breaker: prefer cases with more total pairs
                if score > best_score or (score == best_score and len(case_pairs) > len(best_new_pairs)):
                    best_case = case
                    best_score = score
                    best_new_pairs = new_pairs

            if best_case is None:
                break

            # Add the best case
            selected_cases.append(best_case)
            covered_pairs.update(best_new_pairs)
            remaining_cases.remove(best_case)

            # Update suppressed service counts
            for service in best_case["services"]:
                if service in service_counts:
                    service_counts[service] += 1

            # Progress update every 10 cases
            if len(selected_cases) % 10 == 0:
                coverage = len(covered_pairs) / total_pairs * 100
                print(
                    f"  Selected {len(selected_cases)} cases, "
                    f"coverage: {len(covered_pairs)}/{total_pairs} ({coverage:.1f}%)"
                )

        coverage = len(covered_pairs) / total_pairs * 100
        print(f"\nFinal selection: {len(selected_cases)} cases")
        print(f"Coverage: {len(covered_pairs)}/{total_pairs} pairs ({coverage:.1f}%)")

        # Print suppressed service counts
        if suppressed_services:
            print("\nSuppressed service counts:")
            for service, limit in suppressed_services.items():
                actual = service_counts.get(service, 0)
                print(f"  {service}: {actual}/{limit}")

        return selected_cases

    def save_selected_cases(self, selected_cases: list[dict[str, Any]], output_path: Path):
        """Save selected case names to a file.

        Args:
            selected_cases: List of selected case metadata
            output_path: Path to output file
        """
        with open(output_path, "w") as f:
            for case in selected_cases:
                f.write(f"{case['case_name']}\n")

        print(f"\nSaved {len(selected_cases)} case names to {output_path}")

    def visualize_selected_cases(
        self, selected_cases: list[dict[str, Any]], output_dir: Path, all_cases: list[dict[str, Any]] | None = None
    ):
        """Create visualizations for selected cases.

        Args:
            selected_cases: List of selected case metadata
            output_dir: Output directory for visualizations
            all_cases: Optional list of all cases for comparison
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build DataFrame for selected cases
        selected_records = []
        for case in selected_cases:
            for service in case["services"]:
                selected_records.append({"fault_type": case["fault_type"], "service": service})

        selected_df = pd.DataFrame(selected_records)

        # Create heatmap for selected cases
        self._plot_selected_cases_heatmap(selected_df, output_dir)

        # If all_cases provided, create comparison visualization
        if all_cases:
            all_records = []
            for case in all_cases:
                for service in case["services"]:
                    all_records.append({"fault_type": case["fault_type"], "service": service})
            all_df = pd.DataFrame(all_records)
            self._plot_coverage_comparison(selected_df, all_df, output_dir)

    def _plot_selected_cases_heatmap(self, df: pd.DataFrame, output_dir: Path):
        """Plot heatmap for selected cases."""
        # Create pivot table
        pivot = df.groupby(["fault_type", "service"]).size().reset_index(name="count")
        pivot_table = pivot.pivot(index="service", columns="fault_type", values="count").fillna(0)

        # Sort by total count
        pivot_table["_total"] = pivot_table.sum(axis=1)
        pivot_table = pivot_table.sort_values("_total", ascending=False).drop("_total", axis=1)

        # Limit to top 30 services for readability
        if len(pivot_table) > 30:
            pivot_table = pivot_table.head(30)

        plt.figure(figsize=(18, 12))
        sns.heatmap(
            pivot_table,
            annot=True,
            fmt=".0f",
            cmap="YlGnBu",
            cbar_kws={"label": "Case Count"},
            linewidths=0.5,
            linecolor="gray",
        )
        plt.title(
            f"Selected Cases: Fault Type × Service Distribution\n"
            f"({len(df)} records, {df['fault_type'].nunique()} fault types, "
            f"{df['service'].nunique()} services)",
            fontsize=14,
            fontweight="bold",
        )
        plt.xlabel("Fault Type", fontsize=12)
        plt.ylabel("Service", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_dir / "selected_cases_heatmap.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("  ✓ Saved selected_cases_heatmap.png")

    def _plot_coverage_comparison(self, selected_df: pd.DataFrame, all_df: pd.DataFrame, output_dir: Path):
        """Plot comparison between selected cases and all cases."""
        fig, axes = plt.subplots(1, 2, figsize=(20, 8))

        # Get unique pairs
        selected_pairs = set(zip(selected_df["fault_type"], selected_df["service"], strict=False))
        all_pairs = set(zip(all_df["fault_type"], all_df["service"], strict=False))

        # Create binary pivot tables (1 if pair exists, 0 otherwise)
        all_fault_types = sorted(all_df["fault_type"].unique())

        # Limit to top 25 services for readability
        top_services = all_df["service"].value_counts().head(25).index.tolist()

        # All cases
        all_matrix = pd.DataFrame(0, index=top_services, columns=all_fault_types)
        for fault_type, service in all_pairs:
            if service in top_services:
                all_matrix.loc[service, fault_type] = 1

        # Selected cases
        selected_matrix = pd.DataFrame(0, index=top_services, columns=all_fault_types)
        for fault_type, service in selected_pairs:
            if service in top_services:
                selected_matrix.loc[service, fault_type] = 1

        # Plot all cases
        sns.heatmap(
            all_matrix,
            ax=axes[0],
            cmap="Greys",
            cbar=False,
            linewidths=0.5,
            linecolor="lightgray",
            square=False,
        )
        axes[0].set_title(f"All Cases Coverage\n({len(all_pairs)} unique pairs)", fontsize=12, fontweight="bold")
        axes[0].set_xlabel("Fault Type", fontsize=10)
        axes[0].set_ylabel("Service (Top 25)", fontsize=10)
        axes[0].tick_params(axis="x", rotation=45, labelsize=8)
        axes[0].tick_params(axis="y", labelsize=8)

        # Plot selected cases
        sns.heatmap(
            selected_matrix,
            ax=axes[1],
            cmap="Blues",
            cbar=False,
            linewidths=0.5,
            linecolor="lightgray",
            square=False,
        )
        coverage_pct = len(selected_pairs) / len(all_pairs) * 100
        axes[1].set_title(
            f"Selected Cases Coverage\n({len(selected_pairs)} pairs, {coverage_pct:.1f}% coverage)",
            fontsize=12,
            fontweight="bold",
        )
        axes[1].set_xlabel("Fault Type", fontsize=10)
        axes[1].set_ylabel("Service (Top 25)", fontsize=10)
        axes[1].tick_params(axis="x", rotation=45, labelsize=8)
        axes[1].tick_params(axis="y", labelsize=8)

        plt.tight_layout()
        plt.savefig(output_dir / "coverage_comparison.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("  ✓ Saved coverage_comparison.png")

    def create_visualizations(
        self, df: pd.DataFrame, edge_counter: Counter, output_dir: Path, top_n_edges: int = 30, min_edge_count: int = 5
    ):
        """Create two key visualizations.

        Args:
            df: Fault-service DataFrame
            edge_counter: Counter of service edge frequencies
            output_dir: Output directory
            top_n_edges: Only keep top N edges by frequency (default: 30)
            min_edge_count: Minimum edge count threshold (default: 5)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        sns.set_style("whitegrid")

        print("Creating visualizations...")

        # 1. Fault Type × Service Heatmap
        self._plot_fault_service_heatmap(df, output_dir)

        # 2. Service Dependency Graph
        self._plot_service_dependency_graph(edge_counter, output_dir, top_n_edges, min_edge_count)

        print(f"Visualizations saved to {output_dir}")

    def _plot_fault_service_heatmap(self, df: pd.DataFrame, output_dir: Path):
        """Plot (fault_type, service) distribution heatmap."""
        # Create pivot table
        pivot = df.groupby(["fault_type", "service"]).size().reset_index(name="count")
        pivot_table = pivot.pivot(index="service", columns="fault_type", values="count").fillna(0)

        # Plot top 20 services
        top_services = df["service"].value_counts().head(20).index
        pivot_table = pivot_table.loc[pivot_table.index.isin(top_services)]

        plt.figure(figsize=(16, 10))
        sns.heatmap(pivot_table, annot=True, fmt=".0f", cmap="YlOrRd", cbar_kws={"label": "Case Count"})
        plt.title("Fault Type × Service Distribution (Top 20 Services)", fontsize=14, fontweight="bold")
        plt.xlabel("Fault Type", fontsize=12)
        plt.ylabel("Service", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(output_dir / "fault_service_heatmap.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("  ✓ Saved fault_service_heatmap.png")

    def _plot_service_dependency_graph(
        self, edge_counter: Counter, output_dir: Path, top_n_edges: int = 30, min_edge_count: int = 5
    ):
        """Plot service dependency graph with edge thickness indicating propagation frequency.

        Args:
            edge_counter: Counter of (source, target) edge frequencies
            output_dir: Output directory
            top_n_edges: Only keep top N edges by frequency (default: 30)
            min_edge_count: Minimum edge count threshold (default: 5)
        """
        if not edge_counter:
            print("  ⚠ No edges to plot in dependency graph")
            return

        # Keep only top N edges with count >= min_edge_count
        top_edges = [(edge, count) for edge, count in edge_counter.most_common(top_n_edges) if count >= min_edge_count]

        if not top_edges:
            print(f"  ⚠ No edges with count >= {min_edge_count}")
            return

        # Build filtered graph
        G = nx.DiGraph()
        for (source, target), count in top_edges:
            G.add_edge(source, target, weight=count)

        print(f"    Filtering: top {len(top_edges)} edges (min count: {min_edge_count})")

        try:
            pos = nx.nx_pydot.graphviz_layout(G, prog="dot", root=None)
        except Exception as e:
            raise RuntimeError(
                "Failed to use graphviz layout. Please ensure graphviz is installed:\n"
                "  - Ubuntu/Debian: sudo apt-get install graphviz\n"
                "  - macOS: brew install graphviz\n"
                "  - Windows: choco install graphviz\n"
                f"Error: {e}"
            ) from e

        # Prepare edge widths (normalize to 2-12 range for better visibility)
        edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
        max_weight = max(edge_weights)
        min_weight = min(edge_weights)
        edge_widths = [
            2 + 10 * (w - min_weight) / (max_weight - min_weight) if max_weight > min_weight else 6
            for w in edge_weights
        ]

        # Color edges by weight (light gray to dark red)
        from matplotlib import cm

        edge_colors = [
            cm.Reds(0.3 + 0.7 * (w - min_weight) / (max_weight - min_weight)) if max_weight > min_weight else "gray"
            for w in edge_weights
        ]

        # Calculate node sizes based on total edge weight (in + out)
        node_weights = {}
        for (src, tgt), count in top_edges:
            node_weights[src] = node_weights.get(src, 0) + count
            node_weights[tgt] = node_weights.get(tgt, 0) + count
        max_node_weight = max(node_weights.values()) if node_weights else 1
        node_sizes = [800 + 2200 * node_weights.get(node, 0) / max_node_weight for node in G.nodes()]

        # Plot
        plt.figure(figsize=(20, 14))
        ax = plt.gca()

        # Draw edges with varying thickness and color
        nx.draw_networkx_edges(
            G,
            pos,
            width=edge_widths,
            alpha=0.7,
            edge_color=edge_colors,
            arrows=True,
            arrowsize=25,
            arrowstyle="-|>",
            connectionstyle="arc3,rad=0.15",
            ax=ax,
            min_source_margin=15,
            min_target_margin=15,
        )

        # Draw nodes with gradient based on degree
        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())
        # Color: more out-degree = source (blue), more in-degree = sink (orange)
        node_colors = []
        for node in G.nodes():
            in_d = in_degrees.get(node, 0)
            out_d = out_degrees.get(node, 0)
            if out_d > in_d:
                node_colors.append("#6baed6")  # Blue - source
            elif in_d > out_d:
                node_colors.append("#fd8d3c")  # Orange - sink
            else:
                node_colors.append("#bdbdbd")  # Gray - balanced

        nx.draw_networkx_nodes(
            G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.9, edgecolors="black", linewidths=1.5, ax=ax
        )

        # Draw labels with white background for readability
        nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold", ax=ax)

        # Add edge weight labels for top edges
        edge_labels = {(u, v): str(G[u][v]["weight"]) for u, v in G.edges()}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7, font_color="darkred", ax=ax)

        plt.title(
            f"Service Fault Propagation Graph (Top {len(top_edges)} Edges)\n"
            f"Blue=source, Orange=sink | Edge thickness & color = frequency",
            fontsize=14,
            fontweight="bold",
        )
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(output_dir / "service_dependency_graph.png", dpi=300, bbox_inches="tight")
        plt.close()
        print("  ✓ Saved service_dependency_graph.png")
        print(f"    - Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
        print(f"    - Edge weight range: {min_weight} - {max_weight}")


def tag_cases_in_db(case_names: list[str], tag: str, dataset: str = "RCABench"):
    """Add a tag to selected cases in the database.

    Args:
        case_names: List of case names to tag
        tag: Tag to add to the cases
        dataset: Dataset name in the database
    """
    from sqlmodel import Session, select

    from sota_rca.runner._fallback_db import EvaluationSample  # was: from utu.db.eval_datapoint import DatasetSample
    from sota_rca.utils.sqlmodel_utils import SQLModelUtils

    case_name_set = set(case_names)
    updated_count = 0

    with Session(SQLModelUtils.get_engine()) as session:
        # Query all samples from the dataset
        samples = session.exec(select(DatasetSample).where(DatasetSample.dataset == dataset)).all()

        for sample in samples:
            # Check if sample's path matches any case name
            meta = sample.meta or {}
            datapack_name = meta.get("datapack_name", "")

            if datapack_name in case_name_set:
                # Add tag to sample
                current_tags = sample.tags or []
                if tag not in current_tags:
                    sample.tags = current_tags + [tag]
                    updated_count += 1

        session.commit()

    print(f"\nDatabase update: Added tag '{tag}' to {updated_count} samples in dataset '{dataset}'")
    return updated_count


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Simplified fault propagation analysis - generates heatmap and dependency graph"
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default="data/rcabench_dataset",
        help="Path to RCABench dataset directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="analysis",
        help="Output directory for results",
    )
    parser.add_argument(
        "--top-n-edges",
        type=int,
        default=30,
        help="Number of top edges to display in dependency graph (default: 30)",
    )
    parser.add_argument(
        "--min-edge-count",
        type=int,
        default=5,
        help="Minimum edge count threshold for dependency graph (default: 5)",
    )
    parser.add_argument(
        "--select-diverse",
        action="store_true",
        help="Select diverse cases to maximize (fault_type, service) pair coverage",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=None,
        help="Target number of cases to select (default: auto-determine for ~80%% coverage)",
    )
    parser.add_argument(
        "--suppress-service",
        type=str,
        action="append",
        metavar="SERVICE:LIMIT",
        help="Limit cases for a service, e.g., --suppress-service ts-ui-dashboard:5. Can be used multiple times.",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Tag to apply to selected cases in the database (requires --select-diverse)",
    )
    parser.add_argument(
        "--db-dataset",
        type=str,
        default="RCABench",
        help="Dataset name in the database for tagging (default: RCABench)",
    )

    args = parser.parse_args()

    # Parse suppressed services
    suppressed_services = {}
    if args.suppress_service:
        for item in args.suppress_service:
            if ":" in item:
                service, limit = item.rsplit(":", 1)
                suppressed_services[service] = int(limit)
            else:
                print(f"Warning: Invalid suppress-service format '{item}', expected 'SERVICE:LIMIT'")

    # Initialize analyzer
    analyzer = FaultPropagationAnalyzer(args.dataset_path)

    # If --select-diverse is specified, run case selection workflow
    if args.select_diverse:
        print("=" * 60)
        print("DIVERSE CASE SELECTION MODE")
        print("=" * 60)

        # Collect case metadata
        case_metadata = analyzer.collect_case_metadata()

        # Select diverse cases
        selected_cases = analyzer.select_diverse_cases(case_metadata, args.target_count, suppressed_services)

        # Save selected case names
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        case_list_file = output_dir / "selected_cases.txt"
        analyzer.save_selected_cases(selected_cases, case_list_file)

        # Create visualizations for selected cases
        print("\nCreating visualizations for selected cases...")
        analyzer.visualize_selected_cases(selected_cases, output_dir, all_cases=case_metadata)

        # Print summary
        print("\n" + "=" * 60)
        print("SELECTION SUMMARY")
        print("=" * 60)
        print(f"Total cases: {len(case_metadata)}")
        print(f"Selected cases: {len(selected_cases)}")
        print(f"Selection rate: {len(selected_cases) / len(case_metadata) * 100:.1f}%")

        # Count unique pairs
        all_pairs = set()
        for case in case_metadata:
            for service in case["services"]:
                all_pairs.add((case["fault_type"], service))

        selected_pairs = set()
        for case in selected_cases:
            for service in case["services"]:
                selected_pairs.add((case["fault_type"], service))

        print(f"\nTotal unique (fault_type, service) pairs: {len(all_pairs)}")
        print(f"Covered pairs: {len(selected_pairs)}")
        print(f"Coverage: {len(selected_pairs) / len(all_pairs) * 100:.1f}%")

        print("\n" + "=" * 60)
        print(f"Results saved to: {output_dir}")
        print(f"  - {case_list_file}")
        print("  - selected_cases_heatmap.png")
        print("  - coverage_comparison.png")
        print("=" * 60)

        # Tag cases in database if --tag is specified
        if args.tag:
            print("\n" + "=" * 60)
            print("TAGGING CASES IN DATABASE")
            print("=" * 60)
            case_names = [case["case_name"] for case in selected_cases]
            tag_cases_in_db(case_names, args.tag, args.db_dataset)
            print(f'\nYou can now run evaluation with: --tags "{args.tag}"')
            print("=" * 60)

        return

    # Otherwise, run standard analysis
    print("Starting analysis...")
    df, edge_counter = analyzer.analyze_all_cases()

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save fault-service distribution
    fault_service_file = output_dir / "fault_service_distribution.csv"
    fault_service_counts = df.groupby(["fault_type", "service"]).size().reset_index(name="count")
    fault_service_counts = fault_service_counts.sort_values("count", ascending=False)
    fault_service_counts.to_csv(fault_service_file, index=False)
    print(f"\nSaved fault-service distribution to {fault_service_file}")

    # Save service edge frequencies
    edge_file = output_dir / "service_edge_frequencies.csv"
    edge_df = pd.DataFrame(
        [{"source": src, "target": tgt, "count": cnt} for (src, tgt), cnt in edge_counter.most_common()]
    )
    edge_df.to_csv(edge_file, index=False)
    print(f"Saved service edge frequencies to {edge_file}")

    # Create visualizations
    print("\nCreating visualizations...")
    analyzer.create_visualizations(df, edge_counter, output_dir, args.top_n_edges, args.min_edge_count)

    # Print summary statistics
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total fault-service records: {len(df)}")
    print(f"Unique fault types: {df['fault_type'].nunique()}")
    print(f"Unique services: {df['service'].nunique()}")
    print(f"Total service edges: {len(edge_counter)}")
    print(f"Total edge occurrences: {sum(edge_counter.values())}")

    print("\nTop 10 Fault Types:")
    for i, (fault_type, count) in enumerate(df["fault_type"].value_counts().head(10).items(), 1):
        print(f"  {i:2}. {fault_type:<25} : {count:>4} cases")

    print("\nTop 10 Services:")
    for i, (service, count) in enumerate(df["service"].value_counts().head(10).items(), 1):
        print(f"  {i:2}. {service:<35} : {count:>4} cases")

    print("\nTop 10 Service Propagation Edges:")
    for i, ((src, tgt), count) in enumerate(edge_counter.most_common(10), 1):
        print(f"  {i:2}. {src:<30} -> {tgt:<30} : {count:>4} times")

    print("\n" + "=" * 60)
    print(f"Results saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
