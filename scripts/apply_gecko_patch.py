"""Apply the noscript-mode patch to a Gecko checkout (argv[1]).

dom.html_parser.noscript_mode: 0 = current Gecko, 1 = Chromium-like
(scripting flag off for any document without a script-enabled window),
2 = whatwg/html#9426 (follow only the browser-wide JS setting, for parsing,
serialization and the UA noscript rule).

Also logs NOSCRIPT_MARKUP lines to stderr when markup is parsed inside
noscript with the scripting flag off (port of Chromium's use counters).
"""

import sys
from pathlib import Path

root = Path(sys.argv[1])


def edit(path, old, new, count=1):
    p = root / path
    s = p.read_text()
    n = s.count(old)
    if n != count:
        sys.exit(f"{path}: expected {count} match(es), found {n}:\n{old}")
    p.write_text(s.replace(old, new))


# Pref.
edit(
    "modules/libpref/init/StaticPrefList.yaml",
    "- name: dom.headingoffset.enabled\n",
    """# 0: current behavior for the HTML parser's scripting flag and noscript
# serialization. 1: Chromium-like (off for any document without a
# script-enabled window). 2: follow only the browser-wide JS setting.
- name: dom.html_parser.noscript_mode
  type: RelaxedAtomicInt32
  value: 0
  mirror: always

- name: dom.headingoffset.enabled
""",
)

# Helper.
edit(
    "dom/base/nsContentUtils.h",
    "  static nsresult ParseDocumentHTML(\n"
    "      const nsAString& aSourceBuffer, Document* aTargetDocument,\n"
    "      bool aScriptingEnabledForNoscriptParsing,\n"
    "      mozilla::dom::Sanitizer* aSanitizer = nullptr,\n"
    "      SanitizerMode aSanitizerMode = SanitizerMode::Unsafe);\n",
    "  static nsresult ParseDocumentHTML(\n"
    "      const nsAString& aSourceBuffer, Document* aTargetDocument,\n"
    "      bool aScriptingEnabledForNoscriptParsing,\n"
    "      mozilla::dom::Sanitizer* aSanitizer = nullptr,\n"
    "      SanitizerMode aSanitizerMode = SanitizerMode::Unsafe,\n"
    "      const char* aNoscriptLogCategory = \"parseDocument\");\n"
    "\n"
    "  // Scripting flag for noscript parsing and serialization per\n"
    "  // dom.html_parser.noscript_mode; aCurrent is the mode 0 value.\n"
    "  static bool NoscriptScriptingFlag(const Document* aDoc, bool aCurrent);\n",
)
edit(
    "dom/base/nsContentUtils.cpp",
    "/* static */\nnsresult nsContentUtils::ParseDocumentHTML(\n"
    "    const nsAString& aSourceBuffer, Document* aTargetDocument,\n"
    "    bool aScriptingEnabledForNoscriptParsing, Sanitizer* aSanitizer,\n",
    "/* static */\n"
    "bool nsContentUtils::NoscriptScriptingFlag(const Document* aDoc,\n"
    "                                           bool aCurrent) {\n"
    "  switch (StaticPrefs::dom_html_parser_noscript_mode()) {\n"
    "    case 1:\n"
    "      return aDoc && aDoc->IsScriptEnabled();\n"
    "    case 2:\n"
    "      return Preferences::GetBool(\"javascript.enabled\", true);\n"
    "    default:\n"
    "      return aCurrent;\n"
    "  }\n"
    "}\n"
    "\n"
    "/* static */\nnsresult nsContentUtils::ParseDocumentHTML(\n"
    "    const nsAString& aSourceBuffer, Document* aTargetDocument,\n"
    "    bool aScriptingEnabledForNoscriptParsing, Sanitizer* aSanitizer,\n",
)

# Serializers (modes 0 and 1 keep the document's state).
edit(
    "dom/base/nsContentUtils.cpp",
    "            MOZ_UNLIKELY(!aParent->OwnerDoc()->IsScriptEnabled())) {",
    "            MOZ_UNLIKELY(!nsContentUtils::NoscriptScriptingFlag(\n"
    "                aParent->OwnerDoc(), aParent->OwnerDoc()->IsScriptEnabled()))) {",
)
edit(
    "dom/serializers/nsHTMLContentSerializer.cpp",
    "       (name == nsGkAtoms::noscript &&\n"
    "        aElement->OwnerDoc()->IsScriptEnabled()) ||",
    "       (name == nsGkAtoms::noscript &&\n"
    "        nsContentUtils::NoscriptScriptingFlag(\n"
    "            aElement->OwnerDoc(), aElement->OwnerDoc()->IsScriptEnabled())) ||",
    count=2,
)

# UA style: in mode 2, hide noscript whenever the browser has JS enabled
# (the profiles used for testing always do).
edit(
    "layout/style/res/html.css",
    "/* Hide noscript elements if scripting is enabled */\n",
    "/* Hide noscript elements if scripting is enabled */\n"
    "@media -moz-pref(\"dom.html_parser.noscript_mode\", 2) {\n"
    "  noscript {\n"
    "    display: none !important;\n"
    "  }\n"
    "}\n",
)

# ParseDocumentHTML category plumbing.
edit(
    "dom/base/nsContentUtils.cpp",
    '    bool aScriptingEnabledForNoscriptParsing, Sanitizer* aSanitizer,\n    SanitizerMode aSanitizerMode) {\n  MOZ_ASSERT(!aSanitizer ||\n',
    '    bool aScriptingEnabledForNoscriptParsing, Sanitizer* aSanitizer,\n    SanitizerMode aSanitizerMode, const char* aNoscriptLogCategory) {\n  MOZ_ASSERT(!aSanitizer ||\n',
)
edit(
    "dom/base/nsContentUtils.cpp",
    "  nsresult rv = sHTMLFragmentParser->ParseDocument(\n"
    "      aSourceBuffer, aTargetDocument, aScriptingEnabledForNoscriptParsing,\n",
    "  nsresult rv = sHTMLFragmentParser->ParseDocument(\n"
    "      aSourceBuffer, aTargetDocument, aScriptingEnabledForNoscriptParsing,\n"
    "      aNoscriptLogCategory,\n",
)
edit(
    "dom/base/DOMParser.cpp",
    "nsContentUtils::ParseDocumentHTML(aStr, document, false);",
    "nsContentUtils::ParseDocumentHTML(\n"
    "        aStr, document, false, nullptr,\n"
    "        nsContentUtils::SanitizerMode::Unsafe, \"DOMParser\");",
)

# String parser.
edit(
    "parser/html/nsHtml5StringParser.h",
    "                         bool aScriptingEnabledForNoscriptParsing,\n"
    "                         mozilla::dom::Sanitizer* aSanitizer,\n",
    "                         bool aScriptingEnabledForNoscriptParsing,\n"
    "                         const char* aNoscriptLogCategory,\n"
    "                         mozilla::dom::Sanitizer* aSanitizer,\n",
)
for mode in ("Unsafe", "Safe"):
    edit(
        "dom/base/Document.cpp",
        "      sanitizeWhileParsing ? sanitizer.get() : nullptr,\n"
        f"      nsContentUtils::SanitizerMode::{mode});\n",
        "      sanitizeWhileParsing ? sanitizer.get() : nullptr,\n"
        f"      nsContentUtils::SanitizerMode::{mode}, \"parseHTMLUnsafe\");\n",
    )

edit(
    "parser/html/nsHtml5StringParser.cpp",
    "  nsresult rv =\n"
    "      Tokenize(aSourceBuffer, doc, true, aAllowDeclarativeShadowRoots);\n",
    "  bool isTemplate = aContextLocalName == nsGkAtoms::_template &&\n"
    "                    aContextNamespace == kNameSpaceID_XHTML;\n"
    "  mTreeBuilder->SetNoscriptLog(\n"
    "      isTemplate ? \"template-fragment\"\n"
    "                 : (doc->GetInnerWindow() ? \"fragment\" : \"windowless-fragment\"),\n"
    "      doc, true);\n"
    "  nsresult rv =\n"
    "      Tokenize(aSourceBuffer, doc,\n"
    "               nsContentUtils::NoscriptScriptingFlag(doc, true),\n"
    "               aAllowDeclarativeShadowRoots);\n",
)
edit(
    "parser/html/nsHtml5StringParser.cpp",
    "    bool aScriptingEnabledForNoscriptParsing,\n"
    "    mozilla::dom::Sanitizer* aSanitizer,\n"
    "    nsContentUtils::SanitizerMode aSanitizerMode) {\n"
    "  MOZ_ASSERT(!aTargetDoc->GetFirstChild());\n",
    "    bool aScriptingEnabledForNoscriptParsing, const char* aNoscriptLogCategory,\n"
    "    mozilla::dom::Sanitizer* aSanitizer,\n"
    "    nsContentUtils::SanitizerMode aSanitizerMode) {\n"
    "  MOZ_ASSERT(!aTargetDoc->GetFirstChild());\n",
)
edit(
    "parser/html/nsHtml5StringParser.cpp",
    "  return Tokenize(aSourceBuffer, aTargetDoc,\n"
    "                  aScriptingEnabledForNoscriptParsing,\n",
    "  mTreeBuilder->SetNoscriptLog(aNoscriptLogCategory, aTargetDoc, true);\n"
    "  return Tokenize(aSourceBuffer, aTargetDoc,\n"
    "                  nsContentUtils::NoscriptScriptingFlag(\n"
    "                      aTargetDoc, aScriptingEnabledForNoscriptParsing),\n",
)

# Stream parser: keep script-execution prevention on the real value.
edit(
    "parser/html/nsHtml5StreamParser.cpp",
    "  bool scriptingEnabled =\n"
    "      mMode == LOAD_AS_DATA ? false : mExecutor->IsScriptEnabled();\n"
    "  mOwner->StartTokenizer(scriptingEnabled);\n",
    "  bool scriptingEnabled =\n"
    "      mMode == LOAD_AS_DATA ? false : mExecutor->IsScriptEnabled();\n"
    "  mozilla::dom::Document* noscriptDoc = mExecutor->GetDocument();\n"
    "  bool noscriptFlag =\n"
    "      nsContentUtils::NoscriptScriptingFlag(noscriptDoc, scriptingEnabled);\n"
    "  mOwner->StartTokenizer(scriptingEnabled, noscriptFlag);\n",
)
edit(
    "parser/html/nsHtml5StreamParser.cpp",
    "  mTreeBuilder->setScriptingEnabled(scriptingEnabled);\n"
    "  mTreeBuilder->SetPreventScriptExecution(\n",
    "  mTreeBuilder->SetNoscriptLog(\n"
    "      mMode == LOAD_AS_DATA\n"
    "          ? \"XHR\"\n"
    "          : (noscriptDoc && noscriptDoc->HasScriptsBlockedBySandbox()\n"
    "                 ? \"sandbox\"\n"
    "                 : \"frame-disabled\"),\n"
    "      noscriptDoc, false);\n"
    "  mTreeBuilder->setScriptingEnabled(noscriptFlag);\n"
    "  mTreeBuilder->SetPreventScriptExecution(\n",
)
edit(
    "parser/html/nsHtml5Parser.h",
    "  void StartTokenizer(bool aScriptingEnabled);",
    "  void StartTokenizer(bool aScriptingEnabled, bool aNoscriptFlag);",
)
edit(
    "parser/html/nsHtml5Parser.cpp",
    "void nsHtml5Parser::StartTokenizer(bool aScriptingEnabled) {",
    "void nsHtml5Parser::StartTokenizer(bool aScriptingEnabled,\n"
    "                                   bool aNoscriptFlag) {",
)
edit(
    "parser/html/nsHtml5Parser.cpp",
    "  mTreeBuilder->SetPreventScriptExecution(!aScriptingEnabled);\n"
    "  mTreeBuilder->setScriptingEnabled(aScriptingEnabled);\n",
    "  mTreeBuilder->SetPreventScriptExecution(!aScriptingEnabled);\n"
    "  mTreeBuilder->setScriptingEnabled(aNoscriptFlag);\n",
)
# document.open()/write() in a script-created parser.
edit(
    "parser/html/nsHtml5Parser.cpp",
    "  mTreeBuilder->setScriptingEnabled(executor->IsScriptEnabled());\n",
    "  {\n"
    "    mozilla::dom::Document* doc = executor->GetDocument();\n"
    "    mTreeBuilder->SetNoscriptLog(\n"
    "        doc && doc->GetInnerWindow() ? \"write\" : \"windowless-write\", doc,\n"
    "        true);\n"
    "    mTreeBuilder->setScriptingEnabled(nsContentUtils::NoscriptScriptingFlag(\n"
    "        doc, executor->IsScriptEnabled()));\n"
    "  }\n",
)

# Detection logging.
edit(
    "parser/html/nsHtml5TreeBuilderHSupplement.h",
    "nsHtml5OplessBuilder* mBuilder;\n",
    "nsHtml5OplessBuilder* mBuilder;\n"
    "\n"
    "nsCString mNoscriptLogCategory;\n"
    "nsCString mNoscriptLogInfo;\n"
    "bool mNoscriptLogged = false;\n"
    "void MaybeLogNoscriptMarkup();\n"
    "\n"
    "public:\n"
    "// Main thread only. Captures the category, document URI and JS caller.\n"
    "void SetNoscriptLog(const char* aCategory, mozilla::dom::Document* aDoc,\n"
    "                    bool aWithCaller);\n"
    "\n"
    "private:\n",
)
cpp = root / "parser/html/nsHtml5TreeBuilderCppSupplement.h"
cpp.write_text(
    cpp.read_text().replace(
        '#include "mozilla/StaticPrefs_dom.h"\n',
        '#include "mozilla/StaticPrefs_dom.h"\n#include "mozilla/SourceLocation.h"\n',
        1,
    )
    + """
void nsHtml5TreeBuilder::SetNoscriptLog(const char* aCategory,
                                        mozilla::dom::Document* aDoc,
                                        bool aWithCaller) {
  mNoscriptLogged = false;
  mNoscriptLogCategory.Assign(aCategory);
  mNoscriptLogInfo.Truncate();
  if (aDoc && aDoc->GetDocumentURI()) {
    aDoc->GetDocumentURI()->GetSpec(mNoscriptLogInfo);
  }
  mNoscriptLogInfo.Append('\\t');
  if (aWithCaller && NS_IsMainThread()) {
    auto loc = mozilla::JSCallingLocation::Get();
    if (loc && loc.mResource.is<nsCString>()) {
      mNoscriptLogInfo.Append(loc.FileName());
      mNoscriptLogInfo.AppendPrintf(":%u", loc.mLine);
    }
  }
}

void nsHtml5TreeBuilder::MaybeLogNoscriptMarkup() {
  if (scriptingEnabled || mNoscriptLogged || mNoscriptLogCategory.IsEmpty()) {
    return;
  }
  for (int32_t i = currentPtr; i >= 0; --i) {
    if (stack[i]->ns == kNameSpaceID_XHTML &&
        stack[i]->name == nsGkAtoms::noscript) {
      mNoscriptLogged = true;
      printf_stderr("NOSCRIPT_MARKUP\\t%d\\t%s\\t%s\\n",
                    StaticPrefs::dom_html_parser_noscript_mode(),
                    mNoscriptLogCategory.get(), mNoscriptLogInfo.get());
      return;
    }
  }
}
"""
)
edit(
    "parser/html/nsHtml5TreeBuilder.cpp",
    "void nsHtml5TreeBuilder::comment(char16_t* buf, int32_t start, int32_t length) {\n"
    "  needToDropLF = false;\n",
    "void nsHtml5TreeBuilder::comment(char16_t* buf, int32_t start, int32_t length) {\n"
    "  MaybeLogNoscriptMarkup();\n"
    "  needToDropLF = false;\n",
)
edit(
    "parser/html/nsHtml5TreeBuilder.cpp",
    "                                  bool selfClosing) {\n"
    "  flushCharacters();\n"
    "  int32_t eltPos;\n",
    "                                  bool selfClosing) {\n"
    "  MaybeLogNoscriptMarkup();\n"
    "  flushCharacters();\n"
    "  int32_t eltPos;\n",
)
edit(
    "parser/html/nsHtml5TreeBuilder.cpp",
    "void nsHtml5TreeBuilder::endTag(nsHtml5ElementName* elementName) {\n",
    "void nsHtml5TreeBuilder::endTag(nsHtml5ElementName* elementName) {\n"
    "  if (elementName->getName() != nsGkAtoms::noscript) {\n"
    "    MaybeLogNoscriptMarkup();\n"
    "  }\n",
)
print("ok")
