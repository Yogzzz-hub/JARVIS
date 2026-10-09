"""Bounded public HTTP retrieval. Search snippets never masquerade as an answer."""
from __future__ import annotations
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
import html
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any
from pydantic import Field
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix='public-web')
_STOP = set('what is are the a an in on and of for about search web online summarise summarize artificial intelligence ai machine learning'.split())
_PRIVATE = re.compile(r'\b(?:my|our|password|otp|secret|token|contact|recipient)\b|@|https?://|[\\/]|\d{5,}', re.I)
_FRESH = re.compile(r'\b(?:latest|today|current|news|price|weather|now)\b', re.I)

def clean_text(text):
    return ' '.join(re.sub(r'[\x00-\x08\x0b-\x1f]', '', html.unescape(html.unescape(text or ''))).split())

def public_url(url):
    try:
        if url.startswith('//'): url = 'https:' + url
        parsed = urllib.parse.urlsplit(url)
        redirect = urllib.parse.parse_qs(parsed.query).get('uddg')
        if redirect: parsed = urllib.parse.urlsplit(redirect[0])
        host = (parsed.hostname or '').lower()
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or parsed.port not in (None, 80, 443): return ''
        if '.' not in host or host.endswith(('.local', '.localhost', '.internal')): return ''
        try:
            if not ipaddress.ip_address(host).is_global: return ''
        except ValueError: pass
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))
    except ValueError: return ''

def validate_public_address(url):
    url = public_url(url)
    if not url: raise ValueError('Only public HTTP sources are allowed')
    parsed = urllib.parse.urlsplit(url)
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('Private source address refused')
    return url

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    max_repeats = 2
    max_redirections = 3
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, validate_public_address(newurl))

def _get(url, limit=262144, timeout=2.5):
    url = validate_public_address(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 JARVIS public research', 'Accept': 'text/html,application/json'})
    with urllib.request.build_opener(PublicRedirect()).open(request, timeout=timeout) as response:
        kind = response.headers.get_content_type()
        if not (kind.startswith('text/') or kind == 'application/json'): raise ValueError('Non-text source refused')
        return response.read(limit).decode(response.headers.get_content_charset() or 'utf-8', errors='replace')

class ResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items, self.capture, self.depth, self.buffer = [], '', 0, []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); classes = attrs.get('class', '').split()
        if self.capture:
            if tag not in ('br', 'img', 'hr', 'input', 'meta', 'link'): self.depth += 1
        elif tag == 'a' and 'result__a' in classes:
            self.items.append(dict(title='', snippet='', url=public_url(attrs.get('href', ''))))
            self.capture, self.depth, self.buffer = 'title', 1, []
        elif 'result__snippet' in classes and self.items:
            self.capture, self.depth, self.buffer = 'snippet', 1, []
    def handle_endtag(self, tag):
        if self.capture:
            self.depth -= 1
            if self.depth <= 0:
                self.items[-1][self.capture] = clean_text(' '.join(self.buffer))
                self.capture = ''
    def handle_data(self, text):
        if self.capture: self.buffer.append(text)

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.parts = [], []
        self.boilerplate_depth = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','nav','header','footer','aside','form','noscript'):
            self.skip.append(tag)
        if self.boilerplate_depth:
            if tag not in ('br','img','hr','input','meta','link'): self.boilerplate_depth += 1
            return
        values = dict(attrs)
        if tag not in ('br','img','hr','input','meta','link') and re.search(r'(?:cookie|consent|navigation|sidebar|breadcrumb)',values.get('id','')+' '+values.get('class',''),re.I):
            self.boilerplate_depth = 1
            return
        if not self.skip and tag in ('p','div','h1','h2','h3','li','br'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if self.skip and tag == self.skip[-1]: self.skip.pop()
        if self.boilerplate_depth:
            self.boilerplate_depth -= 1
            return
        if not self.skip and tag in ('p','div','h1','h2','h3','li'): self.parts.append('\n')
    def handle_data(self, text):
        if not self.skip and not self.boilerplate_depth: self.parts.append(text)
    def text(self):
        return '\n'.join(clean_text(line) for line in ''.join(self.parts).splitlines() if clean_text(line))[:8000]

def relevance(query, title, snippet, url=''):
    anchors = set(re.findall(r'[a-z]{3,}', query.lower())) - _STOP
    if not anchors: return 0.0
    combined = (title+' '+snippet).lower()
    # Direct concept aliases support Tamil evidence without translating sentences.
    if not combined.isascii():
        from jarvis.core.context.conversation import terminology
        for alias,canonical in terminology().items():
            if not alias.isascii(): combined = combined.replace(alias,canonical.lower())
    coverage = sum(word in combined for word in anchors)/len(anchors)
    if coverage < .5: return 0.0
    if ('chrome.google.com/webstore' in url or 'chromewebstore.google.com' in url) and not re.search(r'extension|chrome|store', query, re.I): return 0.0
    # An AI topic must have AI evidence, not a medical-only homonym.
    if re.search(r'\b(?:ai|machine learning|llm)\b', query, re.I) and not re.search(r'\b(?:ai|artificial intelligence|machine learning|llms?|language models?)\b|செயற்கை\s*நுண்ணறிவ|மொழி\s*மாதிரி', combined): return 0.0
    host = (urllib.parse.urlsplit(url).hostname or '').lower()
    quality = host.endswith(('.edu','.gov')) or any(host == d or host.endswith('.'+d) for d in ('ibm.com','openai.com','microsoft.com','google.com','arxiv.org','pytorch.org','tensorflow.org','apache.org','postgresql.org','fastapi.tiangolo.com'))
    if host.endswith('wikipedia.org'): quality = .4
    return .75*coverage + .15*sum(word in title.lower() for word in anchors)/len(anchors) + .1*quality

def _fetch_duckduckgo_instant(query):
    try: return json.loads(_get('https://api.duckduckgo.com/?'+urllib.parse.urlencode(dict(q=query,format='json',no_html=1,skip_disambig=1))))
    except Exception: return {}

def _fetch_duckduckgo_lite_html(query, max_results=8):
    try:
        parser = ResultParser()
        parser.feed(_get('https://html.duckduckgo.com/html/?'+urllib.parse.urlencode({'q':query}), limit=524288))
        return parser.items[:max_results]
    except Exception: return []

def _fetch_source(item):
    parser = PageParser(); parser.feed(_get(item['url']))
    text = parser.text()
    if len(text)<100: return None
    return dict(title=item['title'],url=item['url'],text=text)

def _fetch_bing_rss(query):
    """Public alternate search provider; no browser or credentials."""
    try:
        root = ET.fromstring(_get('https://www.bing.com/search?'+urllib.parse.urlencode(dict(q=query,format='rss'))))
        return [dict(title=clean_text(item.findtext('title','')),snippet=clean_text(item.findtext('description','')),
            url=public_url(item.findtext('link',''))) for item in root.findall('./channel/item')[:8]]
    except Exception: return []

class SearchWebInput(Contract):
    query: str = Field(min_length=1,max_length=512)
    max_results: int = Field(default=5,ge=1,le=10)
class SearchResultItem(Contract):
    title: str
    snippet: str
    url: str
class SearchWebOutput(Contract):
    query: str
    summary: str
    results: list[SearchResultItem]
    count: int
    sources: list[dict] = Field(default_factory=list)
    timings: dict = Field(default_factory=dict)
    source_scores: list[dict] = Field(default_factory=list)
    fetch_count: int = 0
    search_calls: int = 0
    refined: bool = False
    cache_hit: bool = False

class WebSearchTool(Tool):
    definition = ToolDefinition(name='search_web',description='Retrieve relevant public sources using bounded HTTP search, without opening a browser.',input_model=SearchWebInput,output_model=SearchWebOutput,read_only=True,risk=RiskLevel.READ_ONLY,timeout_s=10.0,tags=('web','search','news','information','ai'),execution_method=ExecutionMethod.API)
    def __init__(self):
        self._cache, self._pages, self._lock = OrderedDict(), OrderedDict(), threading.Lock()
    def _cached(self, store, key):
        with self._lock:
            item = store.get(key)
            if not item: return None
            if time.perf_counter()-item[0]>300:
                del store[key]; return None
            store.move_to_end(key); return copy.deepcopy(item[1])
    def _remember(self, store, key, value, capacity):
        with self._lock:
            store[key] = (time.perf_counter(),copy.deepcopy(value))
            store.move_to_end(key)
            while len(store)>capacity: store.popitem(last=False)
    def _search(self, query, deadline):
        futures = [_POOL.submit(_fetch_duckduckgo_instant,query),_POOL.submit(_fetch_duckduckgo_lite_html,query),
            _POOL.submit(_fetch_bing_rss,query)]
        done,_ = wait(futures, timeout=max(0,min(3.2,deadline-time.perf_counter())))
        items = []
        for future in done:
            try:
                result = future.result()
                if isinstance(result, dict):
                    if result.get('AbstractText') and result.get('AbstractURL'):
                        items.append(dict(title=result.get('Heading',''),snippet=result['AbstractText'],url=result['AbstractURL']))
                else:
                    items.extend(r.model_dump() if hasattr(r,'model_dump') else r for r in result)
            except Exception: pass
        for future in futures:
            if future not in done: future.cancel()
        return items
    def run(self, arguments: SearchWebInput | dict[str,Any]):
        args = SearchWebInput(**arguments) if isinstance(arguments,dict) else arguments
        started = time.perf_counter(); deadline = started+9
        query = clean_text(args.query)
        if _PRIVATE.search(query):
            return dict(query=query,summary='Private queries are not sent to public search.',results=[],count=0,sources=[])
        from jarvis.core.context.conversation import terminology
        # Cache only recognized public technical concepts, never arbitrary names.
        cacheable = not _FRESH.search(query) and any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',query,re.I)
            for term in terminology())
        key = (query.casefold(),args.max_results)
        cached = self._cached(self._cache,key) if cacheable else None
        if cached:
            cached.update(cache_hit=True,fetch_count=0,search_calls=0,timings={'retrieval_ms':(time.perf_counter()-started)*1000})
            return cached
        search_ms = ranking_ms = 0.0
        ranked=[]; scores=[]; calls=0; refined=False
        for attempt in range(2):
            point=time.perf_counter(); calls+=3
            items=self._search(query if not attempt else query+' definition explanation',deadline)
            search_ms+=(time.perf_counter()-point)*1000
            point=time.perf_counter(); seen=set()
            for item in items:
                item={k:clean_text(item.get(k,'')) for k in ('title','snippet','url')}
                item['url']=public_url(item['url'])
                if not item['url'] or item['url'] in seen: continue
                seen.add(item['url']); score=relevance(query,item['title'],item['snippet'],item['url'])
                scores.append(dict(url=item['url'],score=round(score,3)))
                if score>=.55: ranked.append((score,item))
            ranking_ms+=(time.perf_counter()-point)*1000
            if ranked or deadline-time.perf_counter()<3.5: break
            refined=True
        ranked.sort(key=lambda row:(-row[0],row[1]['url']))
        results=[row[1] for row in ranked[:args.max_results]]
        point=time.perf_counter(); sources=[]; pending=set(); fetch_count=0
        for item in results[:3]:
            page=self._cached(self._pages,item['url']) if cacheable else None
            if page and relevance(query,page['title'],page['text'],page['url'])>=.55: sources.append(page)
            else:
                pending.add(_POOL.submit(_fetch_source,item)); fetch_count+=1
        fetch_deadline=min(deadline,time.perf_counter()+3.2)
        while pending and len(sources)<2 and time.perf_counter()<fetch_deadline:
            done,pending=wait(pending,timeout=max(0,fetch_deadline-time.perf_counter()),return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    page=future.result()
                    if page and relevance(query,page['title'],page['text'],page['url'])>=.55:
                        sources.append(page)
                        if cacheable: self._remember(self._pages,page['url'],page,128)
                except Exception: pass
        for future in pending: future.cancel()
        sources=sorted(sources,key=lambda row:row['url'])[:2]
        output=dict(query=query,summary=f'Retrieved {len(sources)} relevant public sources.' if sources else 'I could not retrieve reliable content for this topic.',results=results,count=len(results),sources=sources,source_scores=scores,fetch_count=fetch_count,search_calls=calls,refined=refined,cache_hit=False,timings=dict(search_ms=search_ms,ranking_ms=ranking_ms,fetch_ms=(time.perf_counter()-point)*1000,retrieval_ms=(time.perf_counter()-started)*1000))
        if sources and cacheable: self._remember(self._cache,key,output,64)
        return output
