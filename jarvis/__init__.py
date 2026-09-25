"""JARVIS EDGE: local deterministic core, phase 1."""
import re as _re

# The router matches requests against a few thousand distinct regular expressions. Python's default
# compiled-pattern cache holds 512, so without this every request recompiled most of them (~90% of
# routing time). A larger cache keeps them compiled for the life of the process.
if getattr(_re, "_MAXCACHE", 0) < 8192:
    _re._MAXCACHE = 8192
