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
        self.voice = None
        self.voice_error = ""
        self._level_history = [0.0] * 24
        self._last_level_ns = 0

    async def start(self):
        start = now_ns()
        cfg = self.config
        self.writer = PersistenceWriter(self.root / cfg.paths.db, cfg.performance.persistence_queue_size, cfg.database)
        await self.writer.start()
        try:
            self.registry = ToolRegistry()
            from jarvis.core.catalog.app_catalog import AppCatalog
            self.resolver = AppCatalog(cfg.aliases, cache_path=self.root / "data" / "app_catalog_cache.json")
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
                    response_provider=lambda: getattr(self, "service", None) and getattr(self.service, "response", None),
                )
            except TypeError:
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
            self.registry.register_alias("describe_screen", "desktop_ui_snapshot")
            self.registry.register_alias("draft_whatsapp_reply", "reply_whatsapp_message")
            self.registry.register_alias("web_search", "search_web")
            self.registry.register_alias("volume_up", "volume_set")
            self.registry.register_alias("volume_down", "volume_set")
            self.registry.register_alias("mute", "volume_set")
            self.registry.register_alias("unmute", "volume_set")
            self.registry.finalize()
            self.logs = LogQueue(self.root / cfg.paths.logs)
            self.bus = EventBus(cfg.performance.event_queue_size)
            self.metrics = MetricsCollector(self.writer, self.bus, cfg.performance.metric_queue_size)
            self.tasks = TaskManager(self.bus, self.writer)
            self.executor = ExecutionEngine()
            self.verifier = Verifier(cfg.performance.verify_poll_ms, cfg.performance.verify_timeout_ms)
            from jarvis.core.context.resolver import ReferenceResolver
            self.reference_resolver = ReferenceResolver(self.memory)
            self._build_intelligence()
            from jarvis.core.router.router import SmartRouter
            from jarvis.core.router.ollama import DisabledProvider, OllamaProvider
            self.router = SmartRouter(
                app_resolver=self.resolver,
                llm_provider=OllamaProvider(client=self.llm, tool_registry=self.registry) if cfg.features.router_ai else DisabledProvider(),
                tool_registry=self.registry,
                working_memory=self.memory,
                reference_resolver=self.reference_resolver,
            )
            from jarvis.core.agent import AgentRunner
            from jarvis.core.planner.adaptive_planner import AdaptivePlanner
            from jarvis.core.scheduler.scheduler import DAGScheduler
            self.agent = AgentRunner(self.registry, self.executor, self.verifier, client=self.llm,
                                     capability_retriever=self.router.capability_retriever)
            self.service = CommandService(self.registry, self.executor, self.verifier, ResponseEngine(),
                                          self.tasks, self.bus, self.writer, self.metrics, router=self.router,
                                          planner=AdaptivePlanner(registry=self.registry, client=self.llm),
                                          scheduler=DAGScheduler(registry=self.registry, executor=self.executor),
                                          planner_enabled=cfg.features.planner, working_memory=self.memory,
                                          assistant=self.assistant, agent=self.agent, whatsapp_ai=self.whatsapp_ai)
            await self._start_audio()
            self.ready = True
            self.startup = {"event": "JARVIS_READY", "startup_ms": (now_ns() - start) / 1e6,
                            "RAM_MB": psutil.Process().memory_info().rss / 2**20,
                            "tool_count": len(self.registry.list()), "database_status": "ready",
                            "event_loop": type(asyncio.get_running_loop()).__name__}
            logging.getLogger("jarvis.runtime").info("JARVIS_READY %s", self.startup)
            print(self.startup, flush=True)

            if self.root == ROOT:
                # Start FileWatcher and background Stage A + Stage B enrichment AFTER JARVIS_READY
                self.watcher = FileWatcher(
                    db_path=self.root / cfg.paths.db,
                    roots=self.indexer._resolve_roots(),
                    cache=self.search_engine.cache,
                    config=getattr(cfg, "search", None),
                )
                self.watcher.start()

                async def _run_startup_indexing():
                    try:
                        has_files = False
                        with self.indexer._get_connection() as con:
                            con.execute("PRAGMA busy_timeout=5000")
                            row = con.execute("SELECT count(*) FROM files").fetchone()
                            has_files = bool(row and row[0] > 0)
                        if not has_files:
                            await asyncio.to_thread(self.indexer.index_metadata_stage_a)
                    except Exception as exc:
                        logging.getLogger("jarvis.runtime").warning("Startup indexing background error: %s", exc)

                self.indexing_task = asyncio.create_task(_run_startup_indexing())

                # Low-priority periodic application catalog refresh (every 10 minutes)
                async def _run_periodic_catalog_refresh():
                    while getattr(self, "ready", False):
                        await asyncio.sleep(600)
                        try:
                            if hasattr(self, "resolver") and hasattr(self.resolver, "refresh"):
                                await asyncio.to_thread(self.resolver.refresh)
                        except Exception as exc:
                            logging.getLogger("jarvis.runtime").debug("Periodic catalog refresh error: %s", exc)

                self.catalog_refresh_task = asyncio.create_task(_run_periodic_catalog_refresh())

                # Local AI: make sure Ollama is running, warm the fast model, embed pending knowledge.
                self.llm_task = asyncio.create_task(self._prepare_models())
                # Reminders: speak / show / push due reminders.
                self.reminder_task = asyncio.create_task(self._run_reminders())

                # Phase 5 Omnichannel: WhatsApp integration service
                try:
                    from jarvis.integrations.whatsapp.service import WhatsAppIntegrationService
                    self.whatsapp_service = WhatsAppIntegrationService(
                        command_service=self.service,
                        confirmation_manager=getattr(self.executor, "confirmation_manager", None),
                        knowledge_service=getattr(self, "knowledge_service", None),
                        event_bus=self.bus,
                        whatsapp_ai=self.whatsapp_ai,
                        announcer=self._announce,
                    )
                    await self.whatsapp_service.start()
                    if self.service and hasattr(self.service, "registry"):
                        for tn in ("send_whatsapp_message", "read_whatsapp_messages", "summarize_whatsapp_messages"):
                            if self.service.registry.contains(tn):
                                t = self.service.registry.get(tn)
                                t.transport = self.whatsapp_service.transport
                                t.confirmation_manager = getattr(self.service.executor, "confirmation_manager", None)
                except Exception as exc:
                    logging.getLogger("jarvis.runtime").warning("WhatsApp omnichannel service startup failed: %s", exc)
            else:
                self.watcher = None
                self.indexing_task = None
                self.catalog_refresh_task = None
                self.whatsapp_service = None
                self.llm_task = None
                self.reminder_task = None
        except BaseException:
            await self.writer.close()
            raise

    # ------------------------------------------------------------------ intelligence wiring
    def _build_intelligence(self) -> None:
        """One LLM client, one knowledge service, one assistant - shared by every AI feature."""
        from jarvis.core.knowledge.engine import KnowledgeEngine
        from jarvis.core.knowledge.service import KnowledgeService
        from jarvis.core.llm.assistant import Assistant, set_assistant
        from jarvis.core.llm.client import LLMSettings, OllamaClient, set_llm
        from jarvis.integrations.whatsapp.ai import WhatsAppAI, set_whatsapp_ai

        cfg = self.config
        self.llm = OllamaClient(LLMSettings.from_config(cfg))
        set_llm(self.llm)
        knowledge_db = self.root / "db" / "knowledge.db"
        self.knowledge_engine = KnowledgeEngine(knowledge_db)
        self.knowledge_service = KnowledgeService(self.knowledge_engine, search_engine=self.search_engine,
                                                  working_memory=self.memory, embedder=self.llm)
        owner = self._owner_name()
        self.assistant = Assistant(client=self.llm, registry=self.registry, knowledge_service=self.knowledge_service,
                                   owner_name="" if owner == "Boss" else owner)
        set_assistant(self.assistant)
        self.whatsapp_ai = WhatsAppAI(client=self.llm, owner_name=owner)
        set_whatsapp_ai(self.whatsapp_ai)
        for tool in self.registry.list():
            if hasattr(tool, "assistant") and getattr(tool, "assistant") is None:
                tool.assistant = self.assistant
            if hasattr(tool, "knowledge_service") and getattr(tool, "knowledge_service") is None:
                tool.knowledge_service = self.knowledge_service
            if tool.definition.name == "reply_whatsapp_message" and getattr(tool, "ai", None) is None:
                tool.ai = self.whatsapp_ai

    @staticmethod
    def _owner_name() -> str:
        try:
            import tomllib
            path = ROOT.parent / "config" / "whatsapp.toml"
            if path.exists():
                with path.open("rb") as f:
                    return str(tomllib.load(f).get("whatsapp", {}).get("owner_name", "Boss")) or "Boss"
        except Exception:
            pass
        return "Boss"

    async def _prepare_models(self) -> None:
        log = logging.getLogger("jarvis.runtime")
        try:
            up = await self.llm.ensure_server(wait_s=25.0) if self.config.models.auto_start else await self.llm.available(refresh=True)
            if not up:
                log.warning("Ollama is not reachable at %s (%s). AI answers, planning and the agent are offline; "
                            "deterministic commands still work.", self.llm.base_url, self.llm.last_error or "not running")
                self.bus.emit("llm.status", "", reachable=False, error=self.llm.last_error)
                return
            roles = {}
            for role in ("fast", "chat", "planner", "embed"):
                try:
                    roles[role] = await self.llm.resolve(role)
                except Exception:
                    roles[role] = None
            log.info("Local AI ready at %s: %s", self.llm.base_url, roles)
            self.bus.emit("llm.status", "", reachable=True, roles=roles)
            if self.config.models.warm_on_start:
                await self.llm.warm("fast")
                # Load the chat model and evaluate the (static) assistant prompt once, so the first
                # spoken answer starts streaming immediately instead of paying for model load + prefill.
                try:
                    await self.llm.chat(
                        [{"role": "system", "content": self.assistant.system_prompt(True)}, {"role": "user", "content": "hi"}],
                        role="chat", max_tokens=1, timeout=120.0)
                except Exception as exc:
                    log.debug("Chat model warm-up skipped: %s", exc)
            if roles.get("embed"):
                self.knowledge_service.schedule_embedding()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Local AI preparation failed: %s", exc)

    async def _announce(self, text: str, request_id: str = "") -> None:
        """Speak a short notice through the normal response path (no-op when TTS is off)."""
        response = getattr(self.service, "response", None)
        if response is not None and getattr(response, "enabled", False):
            try:
                response.schedule_final(request_id or f"notice_{now_ns()}", text)
            except Exception as exc:
                logging.getLogger("jarvis.runtime").debug("Announcement failed: %s", exc)

    async def _run_reminders(self) -> None:
        from jarvis.tools.system.assistant_tools import get_reminder_service
        service = get_reminder_service()
        while getattr(self, "ready", False):
            try:
                for reminder in await asyncio.to_thread(service.pop_due):
                    self.bus.emit("reminder.due", reminder.id, text=reminder.text)
                    await self._announce(f"Reminder: {reminder.text}.", reminder.id)
                    if self.registry.contains("notification_send"):
                        notifier = self.registry.get("notification_send")
                        try:
                            await asyncio.to_thread(notifier.run, {"title": "JARVIS reminder", "message": reminder.text, "priority": 4})
                        except Exception:
                            pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.getLogger("jarvis.runtime").debug("Reminder loop error: %s", exc)
            await asyncio.sleep(2.0)

    async def _start_audio(self):
        import tomllib
        from jarvis.core.audio.output.player import AudioOutputManager
        from jarvis.core.response.ack_cache import AckCache
        from jarvis.core.tts.manager import TTSManager
        from jarvis.core.tts.piper_engine import PiperEngine

        project = ROOT.parent
        with (project / "config/response.toml").open("rb") as file:
            output_config = tomllib.load(file)
        response = self.service.response
        response.event_bus = self.bus
        loop = asyncio.get_running_loop()
        def output_event(name, request_id, data):
            if not loop.is_closed():
                try:
                    loop.call_soon_threadsafe(lambda: self.bus.emit(name, request_id, **data))
                except RuntimeError:
                    pass
        output = output_config["audio_output"]
        device = output["device"]
        response.audio_output = AudioOutputManager(
            device=None if device == "default" else device, event_callback=output_event)
        tts = output_config["tts"]
        response.tts = TTSManager(piper_engine=PiperEngine(project / tts["model_path"]),
                                  keep_warm=tts["keep_warm"])
        response.ack_cache = AckCache(project / "assets/audio/acks")
        response.ack_enabled = output_config["response"]["ack_enabled"] and self.config.features.tts
        response.enabled = self.config.features.tts
        if response.enabled:
            await asyncio.to_thread(response.warm_up)

        # Initialize PULSE: Parallel User Latency & Status Engine
        from jarvis.core.pulse import PulseEngine
        self.pulse = PulseEngine(
            audio_output=response.audio_output,
            ack_cache=response.ack_cache,
            tts_manager=response.tts,
            event_bus=self.bus,
            race_timer_ms=250.0,
        )
        self.service.pulse = self.pulse

        if not self.config.features.voice:
            return
        from jarvis.core.audio.source import MicSource
        from jarvis.core.audio.hub import AudioHub
        from jarvis.core.audio.pipeline import VoicePipeline
        from jarvis.core.audio.wake import OpenWakeWordEngine
        from jarvis.core.audio.output.barge_in import BargeInController
        from jarvis.core.stt.faster_whisper_engine import FasterWhisperEngine
        from jarvis.core.commands.contracts import CommandRequest
        cfg = self.config.voice
        def cancel_task():
            asyncio.create_task(self.service.handle(CommandRequest(text="cancel", source="voice")))
        mic_dev = None if cfg.device in (None, "", "default") else cfg.device
        self.voice = VoicePipeline(
            hub=AudioHub(MicSource(device=mic_dev), on_frame=self._audio_level),
            wake_engine=OpenWakeWordEngine(model_path=str(project / cfg.model_path), threshold=cfg.threshold),
            stt_engine=FasterWhisperEngine(model=str(project / cfg.stt_model) if (project / cfg.stt_model).exists() else cfg.stt_model, device=cfg.stt_device,
                                          compute_type=cfg.compute_type, initial_prompt=self._stt_vocabulary()),
            command_service=self.service, event_bus=self.bus, response_engine=response,
            barge_in_controller=BargeInController(response.audio_output, cancel_task, enabled=output["barge_in"]),
            wake_enabled=cfg.wake_enabled, ptt_enabled=cfg.ptt_enabled, preroll_ms=cfg.preroll_ms)
        try:
            await self.voice.start()
        except Exception as exc:
            self.voice_error = str(exc)
            logging.getLogger("jarvis.runtime").exception("Voice startup failed")
            await self.voice.stop()
            self.bus.emit("voice.error", "", error=self.voice_error)

    def _stt_vocabulary(self) -> str:
        """Bias Whisper toward words JARVIS commands use (names, apps, contacts)."""
        try:
            from jarvis.core.stt.vocabulary import VocabularyBiasProvider
            terms = ["Jarvis", "WhatsApp", "YouTube", "Spotify", "Chrome", "screenshot", "volume", "brightness", "reminder"]
            try:
                from jarvis.integrations.whatsapp.contact_resolver import ContactResolver
                terms += [c.display_name for c in ContactResolver()._contacts[:25] if c.display_name]
            except Exception:
                pass
            return VocabularyBiasProvider(custom_terms=terms, max_tokens=60).generate_prompt()
        except Exception:
            return ""

    def _audio_level(self, frame):
        import numpy as np
        if frame.timestamp_ns - self._last_level_ns < 50_000_000:
            return
        self._last_level_ns = frame.timestamp_ns
        samples = np.frombuffer(frame.pcm, dtype=np.int16).astype(np.float32) / 32768
        rms = float(np.sqrt(np.mean(samples * samples)))
        self._level_history = self._level_history[1:] + [min(1.0, rms * 15)]
        self.bus.emit("audio.level", "", levels=self._level_history, rms=rms)

    def voice_status(self):
        return {"enabled": self.config.features.voice,
                "running": bool(self.voice and self.voice.is_running),
                "error": self.voice_error or (self.voice.last_error if self.voice else ""),
                "metrics": self.voice.metrics if self.voice else {},
                "last_result": self.voice.last_result if self.voice else None,
                "timeline": self.voice.last_timeline if self.voice else {},
                "tts_enabled": self.service.response.enabled,
                "tts_played": self.service.response.audio_output.total_played,
                "tts_error": self.service.response.audio_output.last_error,
                "hotkey_registered": bool(self.voice and self.voice.ptt_engine._registered)}

    async def close(self):
        self.ready = False
        if hasattr(self, "whatsapp_service") and self.whatsapp_service:
            try:
                await self.whatsapp_service.stop()
            except Exception:
                pass
        if self.voice:
            await self.voice.stop()
        if hasattr(self, "watcher") and self.watcher:
            self.watcher.stop()
        if hasattr(self, "enrichment_task"):
            self.enrichment_task.cancel()
            await asyncio.gather(self.enrichment_task, return_exceptions=True)
        if hasattr(self, "indexing_task") and self.indexing_task:
            self.indexing_task.cancel()
        if hasattr(self, "catalog_refresh_task") and self.catalog_refresh_task:
            self.catalog_refresh_task.cancel()
        for name in ("llm_task", "reminder_task"):
            bg = getattr(self, name, None)
            if bg:
                bg.cancel()
        try:
            await self.service.close()
            await self.router.llm_provider.close()
            if getattr(self, "llm", None) is not None:
                await self.llm.aclose()
            try:
                from jarvis.core.computer.browser.loop import get_browser_loop, run_browser
                from jarvis.tools.system import computer_tools
                manager = computer_tools._browser_manager
                if manager is not None and getattr(manager, "_is_running", False):
                    run_browser(manager.stop(), timeout=10)
                get_browser_loop().stop()
            except Exception:
                pass
            self.search_engine.close()
            await self.service.response.close()
            await self.metrics.close()
            await self.bus.close()
            await self.writer.close()
            try:
                loop = asyncio.get_running_loop()
                if hasattr(loop, "_default_executor") and loop._default_executor is not None:
                    loop._default_executor.shutdown(wait=False, cancel_futures=True)
                    loop._default_executor = None
            except Exception:
                pass
        finally:
            await self.logs.close()
