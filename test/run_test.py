"""
Test script: Agent con server MCP e logging LLM.

Usage:
    python test/run_test.py                  # risposta + report uso LLM (default)
    python test/run_test.py --no-stats       # solo risposta, nessun report
    python test/run_test.py --prompt "..."   # prompt personalizzato
"""

import asyncio
import argparse
import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# -----------------------------------------------------------------------
# Setup paths e soppressione log PRIMA di qualsiasi import di librerie
# -----------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
TEST_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT))

os.environ["LITELLM_LOG"] = "CRITICAL"
os.environ["LITELLM_SUPPRESS_DEBUG_INFO"] = "true"
# 0=WARNING, 1=INFO, 2=DEBUG — usato da fastagent.utils.logging al primo import
os.environ["FASTAGENT_DEBUG"] = "0"

logging.basicConfig(level=logging.WARNING)
for _noisy_log in [
    "fastagent", "litellm", "LiteLLM", "mcp", "openai",
    "httpx", "httpcore", "httpcore.http11", "httpcore.http2",
    "asyncio", "urllib3", "anyio",
]:
    logging.getLogger(_noisy_log).setLevel(logging.WARNING)

# -----------------------------------------------------------------------
# Import dopo la configurazione del logging
# -----------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv(TEST_DIR / ".env")

from fastagent.llm.client import LLMClient
from fastagent.grounding.backends.mcp.provider import MCPProvider
from fastagent.grounding.core.types import SessionConfig, BackendType

import litellm as _litellm
_litellm.set_verbose = False
_litellm.suppress_debug_info = True

# Forza ERROR su tutti i logger dopo che Logger.configure() ha girato.
# Logger.configure(attach_to_root=True) mette gli handler sul root logger:
# impostando livello ERROR sul root, tutti i messaggi WARNING/INFO vengono
# filtrati indipendentemente da quando i logger figli vengono creati.
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.ERROR)
for _h in _root_logger.handlers:
    _h.setLevel(logging.ERROR)
logging.getLogger("fastagent").setLevel(logging.ERROR)

# -----------------------------------------------------------------------
# Costanti
# -----------------------------------------------------------------------
DEFAULT_PROMPT = "Mi dici le ultime 5 news sul turismo ?"
MAX_TURNS = 10


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def build_llm_client() -> LLMClient:
    """Costruisce LLMClient configurato per Azure OpenAI dal .env."""
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    if not api_key or not endpoint:
        print("[ERROR] AZURE_OPENAI_API_KEY e/o AZURE_OPENAI_ENDPOINT non trovati nel .env")
        sys.exit(1)
    return LLMClient(
        model=f"azure/{deployment}",
        api_key=api_key,
        api_base=endpoint,
        api_version=api_version,
        enable_tool_result_summarization=False,
    )


def print_usage_report(summary: dict) -> None:
    """Stampa il report di utilizzo del LLM."""
    width = 62
    endpoint = summary.get("endpoint") or "N/A"
    model = summary.get("model", "N/A")
    totals = summary.get("totals", {})
    calls = summary.get("calls", [])
    ep_display = endpoint if len(endpoint) <= 46 else endpoint[:43] + "..."
    # Each data row: 4-space indent + 18-char label + " : " (3) + value (:>10) = 35 fixed chars
    # pad fills the remaining space to reach width
    pad = " " * (width - 34)

    SEP = chr(9472) * width
    TL = chr(9484); TR = chr(9488); BL = chr(9492); BR = chr(9496)
    ML = chr(9500); MR = chr(9508); V  = chr(9474)

    print(f"\n{TL}{SEP}{TR}")
    print(f"{V}{'  LLM USAGE REPORT':^{width}}{V}")
    print(f"{ML}{SEP}{MR}")
    print(f"{V}  Modello  : {model:<{width - 13}}{V}")
    print(f"{V}  Endpoint : {ep_display:<{width - 13}}{V}")
    print(f"{ML}{SEP}{MR}")

    for i, call in enumerate(calls, 1):
        ts = datetime.fromtimestamp(call.get("timestamp", 0)).strftime("%H:%M:%S")
        label = f"  -- Chiamata #{i} ({ts})"
        print(f"{V}{label:<{width}}{V}")
        print(f"{V}    Prompt tokens     : {call.get('prompt_tokens', 0):>10,}{pad}{V}")
        print(f"{V}    Completion tokens : {call.get('completion_tokens', 0):>10,}{pad}{V}")
        print(f"{V}    Total tokens      : {call.get('total_tokens', 0):>10,}{pad}{V}")

    print(f"{ML}{SEP}{MR}")
    print(f"{V}  -- TOTALI{' ' * (width - 11)}{V}")
    print(f"{V}    Chiamate LLM      : {totals.get('calls', 0):>10}{pad}{V}")
    print(f"{V}    Prompt tokens     : {totals.get('prompt_tokens', 0):>10,}{pad}{V}")
    print(f"{V}    Completion tokens : {totals.get('completion_tokens', 0):>10,}{pad}{V}")
    print(f"{V}    Total tokens      : {totals.get('total_tokens', 0):>10,}{pad}{V}")
    cost = totals.get("estimated_cost_usd")
    cost_str = f"${cost:.6f} USD" if cost is not None else "N/A"
    print(f"{V}    Costo stimato     : {cost_str:>10}{pad}{V}")
    print(f"{BL}{SEP}{BR}")


# -----------------------------------------------------------------------
# Main async
# -----------------------------------------------------------------------

async def run_test(prompt: str, show_stats: bool) -> None:

    # 1. Carica config MCP nel formato nativo FastAgent
    config_path = TEST_DIR / "mcp_servers.json"
    with open(config_path) as f:
        mcp_config = json.load(f)

    server_names = list(mcp_config.get("mcpServers", {}).keys())
    print(f"\n[INFO] Connessione a {len(server_names)} server MCP...")

    provider = MCPProvider(config=mcp_config)
    await provider.initialize()

    # Connetti tutti i server (failsafe: logga errori e continua)
    connected = []
    for server_name in server_names:
        try:
            cfg = SessionConfig(
                session_name=f"mcp-{server_name}",
                backend_type=BackendType.MCP,
                connection_params={"server": server_name},
            )
            await provider.create_session(cfg)
            connected.append(server_name)
            print(f"  OK  {server_name}")
        except Exception as e:
            print(f"  FAIL  {server_name}: {e}")

    if not connected:
        print("[ERROR] Nessun server MCP connesso. Uscita.")
        return

    # 2. Elenca tools dai server connessi
    print(f"\n[INFO] Carico tools dai server connessi...")
    all_tools = await provider.list_tools(use_cache=False)
    print(f"[INFO] {len(all_tools)} tools disponibili.")

    # 3. Carica system prompt
    system_prompt_path = TEST_DIR / "system_prompt.txt"
    if system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8").strip()
        system_prompt = system_prompt.replace("{tools_section}", "")
    else:
        system_prompt = "Sei un assistente AI utile con accesso a tool specializzati."

    # 4. Costruisci LLM client
    llm = build_llm_client()

    # 5. Loop multi-turn: chiama LLM -> esegui tools -> richiama LLM con i risultati
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    print(f"\n[USER] {prompt}\n")
    print("[INFO] Avvio chiamata LLM...\n")

    start_time = time.time()
    total_tool_results = []
    final_answer = ""
    turns = 0

    while turns < MAX_TURNS:
        turns += 1
        result = await llm.complete(messages=messages, tools=all_tools, execute_tools=True)

        tool_results = result.get("tool_results", [])
        total_tool_results.extend(tool_results)

        # Aggiorna i messaggi con il turno corrente (include tool_call + tool results)
        messages = result.get("messages", messages)

        if tool_results:
            for tr in tool_results:
                tc = tr.get("tool_call")
                srv = tr.get("server_name", "?")
                name = tc.function.name if tc else "?"
                try:
                    args = json.loads(tc.function.arguments) if tc else {}
                    args_str = json.dumps(args, ensure_ascii=False)
                except Exception:
                    args_str = getattr(tc, "function", {}).arguments if tc else "{}"
                print(f"[TURN {turns}] Tool: {name}  (server: {srv})")
                print(f"              Args: {args_str}")

        if not result.get("has_tool_calls") or not tool_results:
            # Nessun tool richiesto -> l'LLM ha prodotto la risposta finale
            final_answer = result.get("message", {}).get("content", "") or ""
            break
        # Se ci sono stati tool_calls, il loop richiama l'LLM con i risultati
        # e l'LLM produrra' la risposta in linguaggio naturale nel turno successivo

    elapsed = time.time() - start_time

    # 6. Output risposta
    print("\n" + "=" * 62)
    print("RISPOSTA FINALE:")
    print("=" * 62)
    print(final_answer or "[Nessuna risposta generata]")
    print("=" * 62)

    if total_tool_results:
        print(f"\n[INFO] Tool totali chiamati: {len(total_tool_results)}")
        for tr in total_tool_results:
            tc = tr.get("tool_call")
            srv = tr.get("server_name", "?")
            name = tc.function.name if tc else "?"
            is_error = tr.get("result") and tr["result"].is_error
            status = "ERR" if is_error else "OK"
            print(f"  {status}  {name}  (server: {srv})")

    print(f"\n[INFO] Turn LLM: {turns}  |  Tempo totale: {elapsed:.2f}s")

    # 7. Report utilizzo LLM
    if show_stats:
        summary = llm.get_usage_summary()
        print_usage_report(summary)

    # 8. Chiudi sessioni MCP
    try:
        await asyncio.wait_for(provider._client.close_all_sessions(), timeout=4.0)
    except BaseException:
        pass


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test FastAgent con MCP e logging LLM")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT,
                        help="Prompt da inviare all'agente")
    parser.add_argument("--no-stats", dest="no_stats", action="store_true", default=False,
                        help="Disabilita il report LLM (default: visibile)")
    args = parser.parse_args()
    asyncio.run(run_test(prompt=args.prompt, show_stats=not args.no_stats))


if __name__ == "__main__":
    main()
