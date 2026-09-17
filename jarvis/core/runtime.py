import asyncio
import logging
import psutil
from jarvis.config import ROOT, load
from jarvis.core.commands.service import CommandService
from jarvis.core.events.bus import EventBus
from jarvis.core.executor.engine import ExecutionEngine
from jarvis.core.logging_setup import LogQueue
from jarvis.core.metrics.clock import now_ns
from jarvis.core.metrics.collector import MetricsCollector
from jarvis.core.persistence.writer import PersistenceWriter
from jarvis.core.response.engine import ResponseEngine
from jarvis.core.tasks.manager import TaskManager
from jarvis.core.verifier.service import Verifier
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system.app_resolver import AppResolver
from jarvis.tools.system.native import create_tools, hardware_info

class Runtime:
    def __init__(self, config=None, root=ROOT, tools_factory=create_tools):
        self.config = config or load()
        self.root, self.tools_factory = root, tools_factory
        self.ready = False

    async def start(self):
        start = now_ns()
        cfg = self.config
        self.writer = PersistenceWriter(self.root / cfg.paths.db, cfg.performance.persistence_queue_size, cfg.database)
        await self.writer.start()
        try:
            self.registry = ToolRegistry()
            self.resolver = AppResolver(cfg.aliases)
            await asyncio.to_thread(self.resolver.build)
            hardware = await asyncio.to_thread(hardware_info)

            # Phase 3: File + Knowledge Intelligence components
            from jarvis.memory.search.engine import SearchEngine
            from jarvis.memory.search.indexer import FileIndexer
            from jarvis.memory.search.watcher import FileWatcher
            from jarvis.memory.working_memory import WorkingMemory

            self.memory = WorkingMemory()
            self.search_engine = SearchEngine(
                db_path=self.root / cfg.paths.db,
                working_memory=self.memory,
            )
            self.indexer = FileIndexer(
                db_path=self.root / cfg.paths.db,
                config=getattr(cfg, "search", None),
            )

            try:
                tools = self.tools_factory(
                    self.resolver,
                    hardware,
                    search_engine=self.search_engine,
                    working_memory=self.memory,
                )
            except TypeError:
                tools = self.tools_factory(self.resolver, hardware)

            self.registry.discover(tools)
            self.registry.finalize()
            self.logs = LogQueue(self.root / cfg.paths.logs)
            self.bus = EventBus(cfg.performance.event_queue_size)
            self.metrics = MetricsCollector(self.writer, self.bus, cfg.performance.metric_queue_size)
            self.tasks = TaskManager(self.bus, self.writer)
            self.executor = ExecutionEngine()
            self.verifier = Verifier(cfg.performance.verify_poll_ms, cfg.performance.verify_timeout_ms)
            from jarvis.core.router.router import SmartRouter
            self.router = SmartRouter(app_resolver=self.resolver)
            self.service = CommandService(self.registry, self.executor, self.verifier, ResponseEngine(),
                                          self.tasks, self.bus, self.writer, self.metrics, router=self.router)
            self.ready = True
            self.startup = {"event": "JARVIS_READY", "startup_ms": (now_ns() - start) / 1e6,
                            "RAM_MB": psutil.Process().memory_info().rss / 2**20,
                            "tool_count": len(self.registry.list()), "database_status": "ready",
                            "event_loop": type(asyncio.get_running_loop()).__name__}
            logging.getLogger("jarvis.runtime").info("JARVIS_READY %s", self.startup)
            print(self.startup, flush=True)

            # Start FileWatcher and background enrichment AFTER JARVIS_READY
            self.watcher = FileWatcher(
                db_path=self.root / cfg.paths.db,
                roots=self.indexer._resolve_roots(),
                cache=self.search_engine.cache,
                config=getattr(cfg, "search", None),
            )
            self.watcher.start()
            asyncio.create_task(self.indexer.run_enrichment_stage_b())
        except BaseException:
            await self.writer.close()
            raise

    async def close(self):
        self.ready = False
        if hasattr(self, "watcher") and self.watcher:
            self.watcher.stop()
        try:
            await self.service.close()
            await self.metrics.close()
            await self.bus.close()
            await self.writer.close()
        finally:
            await self.logs.close()
