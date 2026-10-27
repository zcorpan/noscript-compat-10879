// Preload script (all frames) for trace.py: follows what scripts do with markup inside <noscript>
// that a parse with the scripting flag off turns into elements. Wraps the parse entry points
// (DOMParser, Document.parseHTMLUnsafe, innerHTML/outerHTML/insertAdjacentHTML/setHTMLUnsafe on
// elements in windowless documents and template, createContextualFragment, document.write in
// windowless documents, XHR responseXML), marks the elements that came from noscript content
// (descendants of noscript, and elements the head insertion mode hoisted out of a noscript), and
// reports queries, serialization and text reads on parsed trees, clones, and insertion of marked
// nodes into the live document. Events go to console.debug as "NSTRACE <json>".
// In mode 2 (#9426) the same parses produce raw text, so the same events show what scripts see then.
() => {
  try { performance.setResourceTimingBufferSize(10000); } catch (e) {}
  const debug = console.debug.bind(console);
  const qsa = Element.prototype.querySelectorAll;
  const dqsa = Document.prototype.querySelectorAll;
  const fqsa = DocumentFragment.prototype.querySelectorAll;
  const getRoot = Node.prototype.getRootNode;
  const innerHTMLGet = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML').get;
  const textGet = Object.getOwnPropertyDescriptor(Node.prototype, 'textContent').get;
  const nsEls = new WeakSet();     // noscript elements from traced parses
  const derived = new WeakMap();   // element from noscript content -> 'inside' | 'hoisted'
  const roots = new WeakMap();     // parsed root (document/fragment/element) -> parse id
  const ids = new WeakMap();       // noscript or derived node -> parse id
  const seen = new Set();
  let nextId = 1, active = false;
  const MARKUP = /<noscript\b[^>]*>([\s\S]*?)<\/noscript/gi;
  const KEY_TAGS = new Set(['IMG', 'IFRAME', 'LINK', 'STYLE', 'SCRIPT', 'A', 'PICTURE', 'SOURCE', 'VIDEO', 'META', 'DIV', 'P', 'SPAN', 'FORM', 'INPUT']);

  const clean = s => String(s).replace(/([a-z][a-z0-9+.-]*:\/\/[^\s?#"'<>]+)[?#][^\s"'<>]*/gi, '$1');
  const short = (s, n) => clean(s).replace(/\s+/g, ' ').slice(0, n);
  function __nstCaller() {
    const frames = (new Error().stack || '').split('\n').filter(l => l && !l.includes('__nst'));
    return frames.slice(0, 4).map(f => clean(f).slice(0, 200));
  }
  function emit(ev) {
    try { debug('NSTRACE ' + JSON.stringify(ev)); } catch (e) {}
  }
  function once(key, ev) {
    if (seen.has(key) || seen.size > 3000) return;
    seen.add(key);
    emit(ev);
  }
  function all(root, sel) {
    if (root instanceof Document) return dqsa.call(root, sel);
    if (root instanceof DocumentFragment) return fqsa.call(root, sel);
    if (root instanceof Element) return qsa.call(root, sel);
    return [];
  }
  function sig(el) {
    const u = el.getAttribute('src') || el.getAttribute('href') || el.getAttribute('data-src') || '';
    return u ? el.tagName + ' ' + u : '';
  }
  function inputNoscripts(input) {
    const out = [];
    if (typeof input !== 'string' || !/<noscript/i.test(input)) return out;
    let m;
    MARKUP.lastIndex = 0;
    while ((m = MARKUP.exec(input)) && out.length < 50) {
      if (/<[a-z!]|&/i.test(m[1])) out.push(m[1]);
    }
    return out;
  }
  function sigsOf(contents) {
    const set = new Set();
    for (const c of contents) {
      const re = /<([a-z][a-z0-9]*)\b[^>]*?\b(?:src|href|data-src)\s*=\s*["']?([^"'\s>]+)/gi;
      let m;
      while ((m = re.exec(c))) set.add(m[1].toUpperCase() + ' ' + m[2]);
    }
    return set;
  }

  function __nstProcess(root, input, entry) {
    try {
      if (!root) return;
      const noscripts = [...all(root, 'noscript')];
      const contents = inputNoscripts(input);
      const withMarkup = noscripts.filter(n => n.firstElementChild || /<[a-z!]|&/i.test(textGet.call(n)));
      if (!withMarkup.length && !contents.length && !(entry === 'XHR' && noscripts.length)) return;
      const id = nextId++;
      active = true;
      roots.set(root, id);
      if (root instanceof HTMLTemplateElement) roots.set(root.content, id);
      let inside = 0, hoisted = 0;
      const tags = {};
      for (const n of noscripts) {
        nsEls.add(n);
        ids.set(n, id);
        for (const d of qsa.call(n, '*')) {
          derived.set(d, 'inside');
          ids.set(d, id);
          inside++;
          tags[d.tagName] = (tags[d.tagName] || 0) + 1;
        }
      }
      const sigs = sigsOf(contents);
      if (sigs.size) {
        for (const el of all(root, '*')) {
          if (derived.has(el) || !KEY_TAGS.has(el.tagName) || el.closest('noscript')) continue;
          const s = sig(el);
          if (s && sigs.has(s)) {
            derived.set(el, 'hoisted');
            ids.set(el, id);
            hoisted++;
            tags[el.tagName] = (tags[el.tagName] || 0) + 1;
          }
        }
      }
      emit({t: 'parse', id, entry, caller: __nstCaller(), doc: location.origin + location.pathname,
            noscripts: noscripts.length, withMarkup: withMarkup.length, inside, hoisted, tags,
            content: contents.slice(0, 5).map(c => short(c, 300)),
            parsed: withMarkup.slice(0, 5).map(n => short(innerHTMLGet.call(n), 300))});
    } catch (e) {}
  }

  function rootId(node) {
    if (!active || !node) return 0;
    try {
      let r = roots.get(node);
      if (r) return r;
      const root = getRoot.call(node);
      r = roots.get(root);
      if (r) return r;
      if (node.ownerDocument) return roots.get(node.ownerDocument) || 0;
    } catch (e) {}
    return 0;
  }
  function count(result) {
    if (!result) return [0, 0];
    if (result instanceof Element) return [derived.has(result) || nsEls.has(result) ? 1 : 0, 1];
    let n = 0, total = 0;
    for (const el of result) {
      total++;
      if (derived.has(el)) n++;
    }
    return [n, total];
  }

  // Queries on parsed trees.
  function wrapQuery(proto, name) {
    const orig = proto[name];
    if (!orig) return;
    proto[name] = {[name]: function __nstQuery(...args) {
      const result = orig.apply(this, args);
      const id = rootId(this);
      if (id) {
        const [n, total] = count(result);
        const caller = __nstCaller();
        once(`q|${id}|${name}|${args[0]}|${caller[0]}|${n}`,
             {t: 'query', id, api: name, sel: short(args[0], 120), derived: n, total, caller});
      }
      return result;
    }}[name];
  }
  for (const proto of [Document.prototype, Element.prototype, DocumentFragment.prototype]) {
    for (const name of ['querySelector', 'querySelectorAll', 'getElementsByTagName', 'getElementsByClassName', 'getElementById']) {
      wrapQuery(proto, name);
    }
  }
  for (const name of ['images', 'links', 'scripts', 'forms']) {
    const desc = Object.getOwnPropertyDescriptor(Document.prototype, name);
    if (!desc || !desc.get) continue;
    Object.defineProperty(Document.prototype, name, {...desc, get: function __nstColl() {
      const result = desc.get.call(this);
      const id = active && roots.get(this);
      if (id) {
        const [n, total] = count(result);
        const caller = __nstCaller();
        once(`c|${id}|${name}|${caller[0]}|${n}`, {t: 'query', id, api: 'document.' + name, sel: '', derived: n, total, caller});
      }
      return result;
    }});
  }

  // Serialization and text reads of trees that hold a traced noscript.
  function holdsNoscript(node) {
    if (nsEls.has(node) || derived.has(node)) return true;
    const list = all(node, 'noscript');
    for (const n of list) if (nsEls.has(n)) return true;
    return false;
  }
  function wrapGetter(proto, name, label) {
    const desc = Object.getOwnPropertyDescriptor(proto, name);
    if (!desc || !desc.get) return;
    Object.defineProperty(proto, name, {...desc, get: function __nstGet() {
      const value = desc.get.call(this);
      if (active) {
        const id = ids.get(this) || rootId(this);
        if (id && holdsNoscript(this)) {
          const caller = __nstCaller();
          once(`s|${id}|${label}|${caller[0]}`, {t: label, id, api: name, len: String(value).length, caller});
        }
      }
      return value;
    }});
  }
  wrapGetter(Element.prototype, 'innerHTML', 'serialize');
  wrapGetter(Element.prototype, 'outerHTML', 'serialize');
  wrapGetter(Node.prototype, 'textContent', 'read-text');
  wrapGetter(HTMLElement.prototype, 'innerText', 'read-text');
  for (const [proto, name] of [[Element.prototype, 'getHTML'], [XMLSerializer.prototype, 'serializeToString']]) {
    const orig = proto[name];
    if (!orig) continue;
    proto[name] = {[name]: function __nstSer(...args) {
      const value = orig.apply(this, args);
      const node = proto === XMLSerializer.prototype ? args[0] : this;
      if (active && node) {
        const id = ids.get(node) || rootId(node) || (node instanceof Document && roots.get(node));
        if (id && holdsNoscript(node)) {
          const caller = __nstCaller();
          once(`s|${id}|${name}|${caller[0]}`, {t: 'serialize', id, api: name, len: String(value).length, caller});
        }
      }
      return value;
    }}[name];
  }

  // Clones keep the marks, so insertion of a clone is still attributed.
  function copyMarks(src, dst) {
    if (!active || !src || !dst) return;
    const id = ids.get(src) || rootId(src);
    if (!id) return;
    const a = [src, ...all(src, '*')], b = [dst, ...all(dst, '*')];
    if (a.length !== b.length) return;
    for (let i = 0; i < a.length; i++) {
      if (nsEls.has(a[i])) { nsEls.add(b[i]); ids.set(b[i], id); }
      if (derived.has(a[i])) { derived.set(b[i], derived.get(a[i])); ids.set(b[i], id); }
    }
    roots.set(dst, id);
  }
  const cloneNode = Node.prototype.cloneNode;
  Node.prototype.cloneNode = function __nstCloneNode(deep) {
    const c = cloneNode.call(this, deep);
    if (deep) copyMarks(this, c);
    return c;
  };
  const importNode = Document.prototype.importNode;
  Document.prototype.importNode = function __nstImportNode(node, deep) {
    const c = importNode.call(this, node, deep);
    if (deep) copyMarks(node, c);
    return c;
  };

  // Parse entry points.
  const windowless = node => {
    const doc = node instanceof Document ? node : node && node.ownerDocument;
    return !!doc && !doc.defaultView;
  };
  const dp = DOMParser.prototype.parseFromString;
  DOMParser.prototype.parseFromString = function __nstParseFromString(str, type) {
    const doc = dp.call(this, str, type);
    if (/html/i.test(type) && /<noscript/i.test(str)) __nstProcess(doc, str, 'DOMParser');
    return doc;
  };
  if (Document.parseHTMLUnsafe) {
    const p = Document.parseHTMLUnsafe;
    Document.parseHTMLUnsafe = function __nstParseHTMLUnsafe(str, ...rest) {
      const doc = p.call(this, str, ...rest);
      if (/<noscript/i.test(String(str))) __nstProcess(doc, String(str), 'parseHTMLUnsafe');
      return doc;
    };
  }
  function wrapSetter(proto, name, rootOf) {
    const desc = Object.getOwnPropertyDescriptor(proto, name);
    if (!desc || !desc.set) return;
    Object.defineProperty(proto, name, {...desc, set: function __nstSet(v) {
      const parent = this.parentNode;
      desc.set.call(this, v);
      const s = String(v);
      if (/<noscript/i.test(s) && (this instanceof HTMLTemplateElement || windowless(this))) {
        __nstProcess(rootOf(this, parent), s, this instanceof HTMLTemplateElement ? 'template' : 'windowless-' + name);
      }
    }});
  }
  wrapSetter(Element.prototype, 'innerHTML', el => el instanceof HTMLTemplateElement ? el.content : el);
  wrapSetter(Element.prototype, 'outerHTML', (el, parent) => parent);
  for (const name of ['insertAdjacentHTML', 'setHTMLUnsafe']) {
    const orig = Element.prototype[name];
    if (!orig) continue;
    Element.prototype[name] = {[name]: function __nstInsert(...args) {
      const r = orig.apply(this, args);
      const s = String(args[args.length === 1 ? 0 : name === 'insertAdjacentHTML' ? 1 : 0]);
      if (/<noscript/i.test(s) && (this instanceof HTMLTemplateElement || windowless(this))) {
        const root = this instanceof HTMLTemplateElement ? this.content : (name === 'insertAdjacentHTML' && this.parentNode) || this;
        __nstProcess(root, s, this instanceof HTMLTemplateElement ? 'template' : 'windowless-' + name);
      }
      return r;
    }}[name];
  }
  const ccf = Range.prototype.createContextualFragment;
  Range.prototype.createContextualFragment = function __nstCCF(s) {
    const f = ccf.call(this, s);
    if (/<noscript/i.test(String(s)) && windowless(this.startContainer)) __nstProcess(f, String(s), 'windowless-createContextualFragment');
    return f;
  };
  for (const name of ['write', 'writeln']) {
    const orig = Document.prototype[name];
    Document.prototype[name] = {[name]: function __nstWrite(...args) {
      const r = orig.apply(this, args);
      const s = args.join('');
      if (!this.defaultView && /<noscript/i.test(s)) __nstProcess(this, s, 'windowless-write');
      return r;
    }}[name];
  }
  const xhrDone = new WeakSet();
  for (const name of ['responseXML', 'response']) {
    const rx = Object.getOwnPropertyDescriptor(XMLHttpRequest.prototype, name);
    if (!rx || !rx.get) continue;
    Object.defineProperty(XMLHttpRequest.prototype, name, {...rx, get: function __nstXHR() {
      const doc = rx.get.call(this);
      if (doc instanceof Document && !xhrDone.has(doc) && doc.contentType === 'text/html') {
        xhrDone.add(doc);
        __nstProcess(doc, '', 'XHR');
      }
      return doc;
    }});
  }

  // Insertion of marked nodes into the live document.
  function watch() {
    new MutationObserver(records => {
      if (!active) return;
      for (const rec of records) {
        for (const node of rec.addedNodes) {
          if (!(node instanceof Element)) continue;
          const list = [node, ...qsa.call(node, '*')];
          if (list.length > 20000) continue;
          const found = {};
          let id = 0;
          for (const el of list) {
            let kind = nsEls.has(el) ? 'noscript' : derived.get(el);
            if (!kind) continue;
            if (kind !== 'noscript') kind += el.parentElement && el.parentElement.closest('noscript') ? '-in-noscript' : '-live';
            id = ids.get(el);
            const k = kind + ':' + el.tagName;
            found[k] = (found[k] || 0) + 1;
          }
          if (id) once(`i|${id}|${Object.keys(found).sort().join(',')}|${rec.target.nodeName}`,
                       {t: 'insert', id, found, into: rec.target.nodeName});
        }
      }
    }).observe(document, {childList: true, subtree: true});
  }
  watch();
}
