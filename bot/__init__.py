"""
Governor Poker Bot — Stealth + Evasion Edition

Modules:
  stealth.py      — human-like mouse movement, timing, anti-detection
  evasion.py      — process camouflage, behavioral profiles, temporal/spatial evasion
  table_reader.py — screen capture, OCR, game state parsing
  executor.py     — action execution (click, type, slider)
  bot_core.py     — main bot loop (read → decide → execute)

Usage:
  python -m bot.bot_core

EDUCATIONAL USE ONLY. Using bots on real-money poker sites
violates Terms of Service and may result in account closure
and fund confiscation.
"""
from .stealth import BezierMouse, HumanTimer, TimingProfile, BetSizingStealth, PatternAvoidance
from .evasion import (EvasionEngine, LogNormalTimer, IdleBehaviorSimulator,
                       EmotionalState, MicroCorrectionMouse, HumanMistakeSimulator,
                       ProfileRotator, SessionPatternGenerator, TrafficSimulator,
                       FingerprintRotator, SESSION_PROFILES, HARDWARE_SEPARATION_GUIDE)
from .table_reader import TableReader, TableConfig, GameState, Street
from .executor import ActionExecutor
from .bot_core import PokerBot, main
