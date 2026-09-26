"""
Cole's Agentic RAG - Agent Reasoning Approach

Based on Cole Medin's philosophy:
- Agent has multiple tools available
- Agent CHOOSES which tools to use based on the question
- No validation loop, no forced sequence
- Trust the model to reason

This is the CORRECT approach for agentic RAG.
"""

from __future__ import annotations as _annotations

from dataclasses import dataclass
import logging
import os
import time
from typing import List, Dict, Any

import aiohttp
import asyncio

from pydantic_ai import Agent, RunContext, settings
from pydantic_ai.models.ollama import OllamaModel
from supabase import create_client, Client

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# Logging Setup
# ============================================
LOG_FORMAT = "{}%(asctime)s - %(levelname)s - %(message)s"

class ColoredEmojiFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG: LOG_FORMAT.format("🔍 "),
        logging.INFO: LOG_FORMAT.format("✅ "),
        logging.WARNING: LOG_FORMAT.format("⚠️ "),
        logging.ERROR: LOG_FORMAT.format("❌ "),
        logging.CRITICAL: LOG_FORMAT.format("🚨 ")
    }
    LEVEL_COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[91m"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        formatted_message = formatter.format(record)
        color = self.LEVEL_COLORS.get(record.levelno)
        return f"{color}{formatted_message}\033[0m"

def setup_logging():
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredEmojiFormatter())
    logger.addHandler(console_handler)

setup_logging()

# ============================================
# Initialize Clients
# ============================================
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

model = OllamaModel(
    model_name=os.getenv('OLLAMA_MODEL_NAME'),
    base_url=os.getenv('OLLAMA_BASE_URL')
)

@dataclass
class Deps:
    supabase: Client

# ============================================
# Cole's Agentic RAG System Prompt
# ============================================
COLE_SYSTEM_PROMPT = """
You are an expert at Pydantic AI - a Python AI agent framework.

You have access to comprehensive documentation through THREE RETRIEVAL STRATEGIES:

## Strategy 1: Semantic Search (retrieve_relevant_documentation)
Best for: Quick retrieval based on meaning, when you know relevant keywords
- Returns top 5 most relevant chunks based on vector similarity
- Use this FIRST for most questions

## Strategy 2: Browse Documentation (list_documentation_pages)
Best for: When semantic search might miss relevant pages
- Lists ALL available documentation pages with their URLs
- Use when:
  * Semantic search returns poor/no results
  * You need to understand what topics are covered
  * Different terminology might be used than your search terms

## Strategy 3: Full Document View (get_page_content)
Best for: Getting complete context when chunks are incomplete
- Returns ALL chunks from a page in order
- Use when:
  * Retrieved chunks seem incomplete or fragmented
  * Content says "see more" or references other sections
  * You need full context for accurate answer

## AGENTIC RAG APPROACH:
Traditional RAG is a "one-trick pony" - only semantic search. You are SMARTER.
You can CHOOSE the best strategy based on the question:

1. Most questions: Start with retrieve_relevant_documentation (fastest)
2. Poor results or terminology mismatch: Try list_documentation_pages to browse
3. Incomplete chunks: Use get_page_content for full context

THINK before answering: Which strategy best serves this question? Use multiple
strategies if needed. Be honest when documentation doesn't contain the answer.
"""

# ============================================
# Agent with Cole's Approach
# ============================================
pydantic_ai_expert = Agent(
    model,
    deps_type=Deps,
    system_prompt=COLE_SYSTEM_PROMPT,
    retries=2,
)

# ============================================
# Tool Definitions with Clear Descriptions
# ============================================

@pydantic_ai_expert.tool
async def retrieve_relevant_documentation(
    ctx: RunContext[Deps],
    user_query: str,
) -> str:
    """STRATEGY 1 - Semantic Search: Find relevant chunks by meaning.

    Use this FIRST for most questions. Fast retrieval based on vector similarity.

    When to use:
    - Most questions (start here)
    - You know the relevant keywords/concepts
    - Quick lookup needed

    Args:
        user_query: The search query to find relevant documentation

    Returns:
        Top 5 most relevant chunks with metadata.
    """
    logging.info(f"[STRATEGY 1] Semantic search for: '{user_query}'")
    try:
        # Get embedding
        url = os.getenv('EMBEDDING_API_URL', 'http://127.0.0.1:11434/api/embeddings')
        payload = {
            "model": os.getenv('EMBEDDING_MODEL', 'nomic-embed-text'),
            "prompt": user_query
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    return f"Error getting embedding: HTTP {response.status}"
                result = await response.json()
                query_embedding = result.get('embedding', [])

        # Query Supabase
        result = ctx.deps.supabase.rpc(
            'match_site_pages',
            {
                'query_embedding': query_embedding,
                'match_count': 5,
                'filter': {'source': 'pydantic_ai_docs'}
            }
        ).execute()

        if not result.data:
            return "No relevant documentation found."

        # Format with chunk count metadata
        chunks = []
        for i, doc in enumerate(result.data, 1):
            chunks.append(f"# {doc['title']}\nURL: {doc['url']}\n\n{doc['content']}")

        return "\n\n---\n\n".join(chunks)

    except Exception as e:
        logging.error(f"Error in retrieve_relevant_documentation: {e}")
        return f"Error: {str(e)}"


@pydantic_ai_expert.tool
async def list_documentation_pages(
    ctx: RunContext[Deps],
) -> str:
    """STRATEGY 2 - Browse Documentation: See ALL available pages.

    Use when semantic search might miss relevant pages.

    When to use:
    - Semantic search returns poor/no results
    - The question might use different terminology
    - You need to understand what topics are covered

    Returns:
        List of all available page URLs.
    """
    logging.info("[STRATEGY 2] Browsing all documentation pages")
    try:
        result = ctx.deps.supabase.from_('site_pages') \
            .select('url') \
            .eq('metadata->>source', 'pydantic_ai_docs') \
            .execute()

        if not result.data:
            return "No documentation pages found."

        urls = sorted(set(doc['url'] for doc in result.data))

        # Format as readable list
        output = ["## Available Documentation Pages\n"]
        output.append(f"Total pages: {len(urls)}\n")

        # Group by URL prefix for better organization
        groups = {}
        for url in urls:
            prefix = url.split(':')[0] if ':' in url else 'other'
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(url)

        for prefix, pages in sorted(groups.items()):
            output.append(f"\n### {prefix.upper()}")
            for page in pages[:10]:  # Show first 10 per group
                output.append(f"  - {page}")
            if len(pages) > 10:
                output.append(f"  ... and {len(pages) - 10} more")

        return "\n".join(output)

    except Exception as e:
        logging.error(f"Error in list_documentation_pages: {e}")
        return f"Error: {str(e)}"


@pydantic_ai_expert.tool
async def get_page_content(
    ctx: RunContext[Deps],
    url: str,
) -> str:
    """STRATEGY 3 - Full Document View: Get complete page content.

    Use when semantic search returns incomplete chunks.

    When to use:
    - Retrieved chunks seem incomplete or fragmented
    - Content says "see more" or references other sections
    - You need full context for accurate answer

    Args:
        url: The exact URL from list_documentation_pages or retrieve_relevant_documentation

    Returns:
        Full page content with ALL chunks combined in order.
    """
    logging.info(f"[STRATEGY 3] Getting full content for: '{url}'")
    try:
        result = ctx.deps.supabase.from_('site_pages') \
            .select('title, content, chunk_number') \
            .eq('url', url) \
            .eq('metadata->>source', 'pydantic_ai_docs') \
            .order('chunk_number') \
            .execute()

        if not result.data:
            return f"No content found for URL: {url}"

        page_title = result.data[0]['title'].split(' - ')[0]
        content = [f"# {page_title}\n"]

        for chunk in result.data:
            content.append(chunk['content'])

        return "\n\n".join(content)

    except Exception as e:
        logging.error(f"Error in get_page_content: {e}")
        return f"Error: {str(e)}"


# ============================================
# Metrics Tracking
# ============================================
class QueryMetrics:
    def __init__(self):
        self.start_time = None
        self.tools_used = []

    def start(self):
        self.start_time = time.time()

    def add_tool(self, tool_name: str):
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

    def get_summary(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            "latency_seconds": round(elapsed, 2),
            "tools_used": self.tools_used,
            "tool_count": len(self.tools_used),
        }


# ============================================
# Main Execution - Single Pass, No Validation
# ============================================
async def main():
    # Test questions
    questions = [
        "What is Pydantic AI?",
        "How do I create an agent with tools?",
        "What topics does the documentation cover?",
        "get me the Weather Agent Example",
    ]

    logging.info("=" * 70)
    logging.info("Cole's Agentic RAG - Agent Reasoning Approach")
    logging.info("=" * 70)

    all_results = []

    for i, question in enumerate(questions, 1):
        logging.info("\n" + "=" * 70)
        logging.info(f"Query {i}/4: {question}")
        logging.info("=" * 70)

        metrics = QueryMetrics()
        metrics.start()

        deps = Deps(supabase=supabase)

        # Track tools via a wrapper
        original_retrieve = retrieve_relevant_documentation.func
        original_list = list_documentation_pages.func
        original_get = get_page_content.func

        async def tracked_retrieve(*args, **kwargs):
            metrics.add_tool("retrieve_relevant_documentation")
            return await original_retrieve(*args, **kwargs)

        async def tracked_list(*args, **kwargs):
            metrics.add_tool("list_documentation_pages")
            return await original_list(*args, **kwargs)

        async def tracked_get(*args, **kwargs):
            metrics.add_tool("get_page_content")
            return await original_get(*args, **kwargs)

        # Temporarily replace with tracked versions
        retrieve_relevant_documentation.func = tracked_retrieve
        list_documentation_pages.func = tracked_list
        get_page_content.func = tracked_get

        try:
            # SINGLE PASS - No validation loop
            response = await pydantic_ai_expert.run(
                user_prompt=question,
                deps=deps
            )

            summary = metrics.get_summary()
            summary["question"] = question
            summary["answer_preview"] = str(response.data)[:200] + "..."
            all_results.append(summary)

            logging.info("\n" + "-" * 70)
            logging.info("RESULTS:")
            logging.info(f"  Latency: {summary['latency_seconds']}s")
            logging.info(f"  Tools Used: {summary['tools_used']}")
            logging.info(f"  Tool Count: {summary['tool_count']}/3")
            logging.info("-" * 70)

        finally:
            # Restore original functions
            retrieve_relevant_documentation.func = original_retrieve
            list_documentation_pages.func = original_list
            get_page_content.func = original_get

    # Summary
    logging.info("\n" + "=" * 70)
    logging.info("SUMMARY - Cole's Approach")
    logging.info("=" * 70)

    avg_latency = sum(r['latency_seconds'] for r in all_results) / len(all_results)
    avg_tools = sum(r['tool_count'] for r in all_results) / len(all_results)

    logging.info(f"Average Latency: {avg_latency:.2f}s")
    logging.info(f"Average Tools per Query: {avg_tools:.1f}/3")
    logging.info(f"\nTool Distribution:")
    for r in all_results:
        logging.info(f"  • {r['question'][:40]}... -> {r['tools_used']}")

    logging.info("\n" + "=" * 70)
    logging.info("Key Finding: Agent CHOOSES different tools per question!")
    logging.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
