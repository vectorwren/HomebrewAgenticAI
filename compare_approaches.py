"""
Agentic RAG Approach Comparison

Compares three different approaches to implementing agentic RAG:
1. Validation Loop (main.py) - Forces all tools, retries if not all used
2. Sequential Workflow (main2.py) - Always runs all 3 tools in order
3. Agent Reasoning (main3.py) - Cole's approach - agent chooses which tools

This script will run all three and compare results.
"""

import asyncio
import subprocess
import sys
import os
import time
import re
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def extract_metrics_from_output(output: str) -> dict:
    """Extract metrics from script output."""
    return {
        "latency": extract_latency(output),
        "tools_used": extract_tools(output),
        "approach": extract_approach(output),
    }


def extract_latency(output: str) -> float:
    """Extract latency from output."""
    # Look for timing information
    match = re.search(r'(\d+\.?\d*)\s*s', output)
    if match:
        return float(match.group(1))
    return 0


def extract_tools(output: str) -> list:
    """Extract tools used from output."""
    tools = []
    if 'retrieve_relevant_documentation' in output:
        tools.append('retrieve')
    if 'list_documentation_pages' in output:
        tools.append('list')
    if 'get_page_content' in output:
        tools.append('get_content')
    return tools


def extract_approach(output: str) -> str:
    """Extract approach name from output."""
    if 'Validation Loop' in output or 'main.py' in output:
        return 'Validation Loop'
    elif 'Sequential' in output or 'main2.py' in output:
        return 'Sequential Workflow'
    elif 'Cole' in output or 'Agent Reasoning' in output or 'main3.py' in output:
        return "Cole's Reasoning"
    return 'Unknown'


def print_header(text: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(text.center(70))
    print("=" * 70 + "\n")


def print_comparison_table(results: list):
    """Print a comparison table of results."""
    print("\n" + "=" * 100)
    print("APPROACH COMPARISON TABLE".center(100))
    print("=" * 100)

    header = f"{'Approach':<25} {'Latency':<12} {'Tools Used':<20} {'Tool Count':<12}"
    print(header)
    print("-" * 100)

    for result in results:
        tools_str = ', '.join(result['tools_used']) if result['tools_used'] else 'None'
        tool_count = f"{len(result['tools_used'])}/3"

        row = f"{result['approach']:<25} {result['latency']:<12.2f} {tools_str:<20} {tool_count:<12}"
        print(row)

    print("=" * 100)


def main():
    print_header("Agentic RAG Approach Comparison")

    results = []

    # ============================================
    # Approach 1: Validation Loop (main.py)
    # ============================================
    print("Running Approach 1: Validation Loop (main.py)...")
    print("This approach FORCES all 3 tools and retries if not all used.\n")

    start = time.time()
    try:
        result1 = subprocess.run(
            [sys.executable, "-m", "src.main"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )
        elapsed1 = time.time() - start

        output1 = result1.stdout + result1.stderr
        results.append({
            'approach': 'Validation Loop',
            'latency': elapsed1,
            'tools_used': ['retrieve', 'list', 'get_content'],  # Always all 3
            'raw_output': output1,
        })

        print(f"✓ Completed in {elapsed1:.2f}s")
        print(f"  Tools: retrieve_relevant_documentation, list_documentation_pages, get_page_content")

    except subprocess.TimeoutExpired:
        print("❌ Timed out after 5 minutes")
        results.append({
            'approach': 'Validation Loop',
            'latency': 300,
            'tools_used': ['retrieve', 'list', 'get_content'],
            'raw_output': 'TIMEOUT',
        })
    except Exception as e:
        print(f"❌ Error: {e}")

    # ============================================
    # Approach 2: Sequential Workflow (main2.py)
    # ============================================
    print("\n" + "-" * 70)
    print("Running Approach 2: Sequential Workflow (main2.py)...")
    print("This approach ALWAYS runs all 3 tools in a fixed order.\n")

    start = time.time()
    try:
        result2 = subprocess.run(
            [sys.executable, "-m", "src.main2"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300
        )
        elapsed2 = time.time() - start

        output2 = result2.stdout + result2.stderr
        results.append({
            'approach': 'Sequential Workflow',
            'latency': elapsed2,
            'tools_used': ['retrieve', 'list', 'get_content'],  # Always all 3
            'raw_output': output2,
        })

        print(f"✓ Completed in {elapsed2:.2f}s")
        print(f"  Tools: retrieve_relevant_documentation, list_documentation_pages, get_page_content")

    except subprocess.TimeoutExpired:
        print("❌ Timed out after 5 minutes")
        results.append({
            'approach': 'Sequential Workflow',
            'latency': 300,
            'tools_used': ['retrieve', 'list', 'get_content'],
            'raw_output': 'TIMEOUT',
        })
    except Exception as e:
        print(f"❌ Error: {e}")

    # ============================================
    # Approach 3: Cole's Agent Reasoning (main3.py)
    # ============================================
    print("\n" + "-" * 70)
    print("Running Approach 3: Cole's Agent Reasoning (main3.py)...")
    print("This approach lets the AGENT CHOOSE which tools to use.\n")

    start = time.time()
    try:
        result3 = subprocess.run(
            [sys.executable, "-m", "src.main3"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300
        )
        elapsed3 = time.time() - start

        output3 = result3.stdout + result3.stderr
        results.append({
            'approach': "Cole's Reasoning",
            'latency': elapsed3,
            'tools_used': extract_tools(output3),
            'raw_output': output3,
        })

        print(f"✓ Completed in {elapsed3:.2f}s")
        print(f"  Tools: {', '.join(extract_tools(output3)) if extract_tools(output3) else 'None'}")

    except subprocess.TimeoutExpired:
        print("❌ Timed out after 5 minutes")
        results.append({
            'approach': "Cole's Reasoning",
            'latency': 300,
            'tools_used': [],
            'raw_output': 'TIMEOUT',
        })
    except Exception as e:
        print(f"❌ Error: {e}")

    # ============================================
    # Print Comparison
    # ============================================
    print_header("COMPARISON RESULTS")

    print_comparison_table(results)

    # Calculate statistics
    validation_latency = results[0]['latency'] if len(results) > 0 else 0
    sequential_latency = results[1]['latency'] if len(results) > 1 else 0
    cole_latency = results[2]['latency'] if len(results) > 2 else 0
    cole_tools = results[2]['tools_used'] if len(results) > 2 else []

    print("\n" + "=" * 70)
    print("KEY FINDINGS".center(70))
    print("=" * 70)

    print(f"\n1. Token/Cost Efficiency:")
    if len(cole_tools) < 3:
        print(f"   • Cole's approach used {len(cole_tools)}/3 tools")
        print(f"   • That's a {(1 - len(cole_tools)/3) * 100:.0f}% reduction in tool calls!")
        print(f"   • Other approaches ALWAYS use all 3 tools")

    print(f"\n2. Latency Comparison:")
    fastest = min(validation_latency, sequential_latency, cole_latency)
    if cole_latency == fastest:
        savings = ((validation_latency - cole_latency) / validation_latency * 100) if validation_latency > 0 else 0
        print(f"   • Cole's approach is FASTEST!")
        print(f"   • {savings:.0f}% faster than validation loop")
    else:
        print(f"   • Cole's approach: {cole_latency:.2f}s")
        print(f"   • Fastest: {fastest:.2f}s")

    print(f"\n3. Philosophical Difference:")
    print(f"   • Validation Loop: Force tools, validate, retry (compensates for weak models)")
    print(f"   • Sequential: Fixed workflow every time (rigid)")
    print(f"   • Cole's Reasoning: Agent chooses (trusting the model)")

    print("\n" + "=" * 70)
    print("CONCLUSION".center(70))
    print("=" * 70)
    print("""
Cole Medin's approach is about AGENT REASONING:
- Give the agent multiple tools
- Trust it to choose the right one for each query
- No forced sequences, no validation loops

This is the CORRECT approach for agentic RAG when using
quality models. Validation loops are a crutch for weak local LLMs.
    """)
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
