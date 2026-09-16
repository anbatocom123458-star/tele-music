"""Persistence layer backed by ChromaDB (HTTP client mode).

Collections (metadata only — no binaries, no vector search):
    users, redeem_codes, conversations, messages,
    usage_logs, voice_generations, svg_generations
"""
