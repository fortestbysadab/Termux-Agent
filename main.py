#!/usr/bin/env python3
"""Main entry point for Termux Agent."""

import argparse
import sys
from config import HOST, PORT
from db import init_db
from connectors.manager import ConnectorManager
from web.server import run_server

def main():
    parser = argparse.ArgumentParser(description="Termux Agent: Autonomous Terminal & MCP Connectors")
    parser.add_argument("--host", default=HOST, help=f"Host to bind (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    args = parser.parse_args()

    print("==================================================")
    print("⚡ Termux Agent — Autonomous Terminal & Connectors")
    print("==================================================")
    print("• Per-session isolated workspaces (/workspace)")
    print("• Full terminal execution (proot jail & subprocess limits)")
    print("• Connectors & Custom MCP (Model Context Protocol)")
    print("• Workspace file artifacts vs. direct chat routing")
    print("• Persistent chat history with delete / clear options")
    print("--------------------------------------------------")

    run_server()

if __name__ == "__main__":
    main()
