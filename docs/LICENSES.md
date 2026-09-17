# Dependency inventory and rationale

Versions below are the installed, tested environment. `requirements-lock.txt`
pins it for reproduction. License information was inspected from each installed
distribution's METADATA and bundled license files (including pycaw and Colorama).
All dependencies are free/open source; none requires a paid service.

| Direct dependency | Version | License | Why stdlib/current dependencies are insufficient |
|---|---|---|---|
| FastAPI | 0.141.1 | MIT | Requested typed ASGI gateway and boundary validation |
| Uvicorn | 0.53.0 | BSD-3-Clause | Requested ASGI HTTP/WebSocket server |
| Pydantic | 2.13.5 | MIT | Requested strict contracts and cached JSON Schema |
| psutil | 7.2.2 | BSD-3-Clause | Portable process and resource inspection unavailable in stdlib |
| mss | 10.2.0 | MIT | Native screenshot capture unavailable in stdlib |
| pycaw | 20251023 | MIT | Windows Core Audio access unavailable in stdlib |
| httptools | 0.8.0 | MIT | Requested efficient HTTP parser for Uvicorn |
| h11 | 0.16.0 | MIT | Uvicorn's pure-Python HTTP fallback |
| websockets | 16.1.1 | BSD-3-Clause | Sans-I/O protocol engine and benchmark client |
| pytest | 9.1.1 | MIT | Requested automated testing |
| pytest-asyncio | 1.4.0 | Apache-2.0 | Async test lifecycle support |
| HTTPX | 0.28.1 | BSD-3-Clause | FastAPI test client support and real async HTTP tests |

| Transitive dependency | Version | License | Purpose |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | FastAPI metadata |
| annotated-types | 0.8.0 | MIT | Pydantic constraints |
| anyio | 4.15.1 | MIT | Starlette/HTTPX async support |
| certifi | 2026.7.22 | MPL-2.0 | HTTPX CA bundle |
| click | 8.5.0 | BSD-3-Clause | Uvicorn CLI |
| colorama | 0.4.6 | BSD-3-Clause | Windows terminal formatting |
| comtypes | 1.4.16 | MIT | pycaw COM bindings |
| httpcore | 1.0.9 | BSD-3-Clause | HTTPX transport |
| idna | 3.19 | BSD-3-Clause | HTTPX hostname handling |
| iniconfig | 2.3.0 | MIT | pytest configuration |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | pytest version handling |
| pluggy | 1.6.0 | MIT | pytest hooks |
| pydantic-core | 2.46.5 | MIT | Pydantic validation engine |
| Pygments | 2.21.0 | BSD-2-Clause | pytest diagnostic highlighting |
| Starlette | 1.6.0 | BSD-3-Clause | FastAPI ASGI framework |
| typing-extensions | 4.16.0 | PSF-2.0 | Type compatibility |
| typing-inspection | 0.4.4 | MIT | Pydantic type introspection |

Python 3.12.14 uses the PSF license; SQLite is public domain. Setuptools is a
build-only MIT dependency. uv 0.12.15 (MIT OR Apache-2.0) was used only to bootstrap
the workspace-local Python and virtual environment because Python 3.12 was absent.
Its Python build distribution includes additional bundled library licenses in
`.runtime/python`; preserve those notices if redistributing that runtime. It is
not an application dependency. No runtime request uses the internet.

Retain upstream copyright/license notices when redistributing dependencies.
The MPL license applies to certifi's covered files. This inventory does not assign
a license to the user's JARVIS project itself.

API references checked during implementation:
[Uvicorn settings](https://www.uvicorn.org/settings/),
[pycaw Core Audio examples](https://andremiras.github.io/pycaw/examples/index.html).
