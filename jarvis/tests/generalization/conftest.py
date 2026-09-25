"""Shared fixtures for Generalization Suite."""

import pytest
from unittest.mock import Mock
from jarvis.config import Config
from jarvis.core.router.router import SmartRouter
from jarvis.core.router.models import RouteLane
from jarvis.core.capabilities.registry import CapabilityRegistry, get_default_capability_registry
from jarvis.core.capabilities.retrieval import CapabilityRetriever
from jarvis.core.context.resolver import ReferenceResolver
from jarvis.core.memory.working import BoundedWorkingMemory
from jarvis.tools.system.app_resolver import AppResolver, LaunchTarget
from jarvis.core.router.ollama import DisabledProvider

@pytest.fixture
def working_memory():
    return BoundedWorkingMemory()

@pytest.fixture
def reference_resolver(working_memory):
    return ReferenceResolver(working_memory)

@pytest.fixture
def app_resolver():
    resolver = AppResolver()
    resolver.cache = {
        "chrome": LaunchTarget("chrome.exe", ("chrome.exe",)),
        "notepad": LaunchTarget("notepad.exe", ("notepad.exe",)),
        "vlc": LaunchTarget("vlc.exe", ("vlc.exe",)),
        "calculator": LaunchTarget("calc.exe", ("calculatorapp.exe",)),
        "spotify": LaunchTarget("spotify.exe", ("spotify.exe",)),
        "vscode": LaunchTarget("code.exe", ("code.exe",)),
    }
    return resolver

@pytest.fixture
def capability_registry():
    return get_default_capability_registry()

@pytest.fixture
def capability_retriever(capability_registry):
    return CapabilityRetriever(capability_registry)

@pytest.fixture
def router(app_resolver, working_memory, reference_resolver, capability_registry, capability_retriever):
    return SmartRouter(
        llm_provider=DisabledProvider(),
        app_resolver=app_resolver,
        working_memory=working_memory,
        reference_resolver=reference_resolver,
        capability_registry=capability_registry,
        capability_retriever=capability_retriever,
    )
