"use client";

import { useMemo, useState } from "react";
import { migrateSource } from "@/lib/migrate";
import { SAMPLES } from "@/lib/samples";

function lineCount(text: string): number {
  return text.split("\n").length;
}

export default function Page() {
  const [sampleId, setSampleId] = useState<(typeof SAMPLES)[number]["id"]>("login");
  const sample = SAMPLES.find((item) => item.id === sampleId) ?? SAMPLES[0];
  const [source, setSource] = useState<string>(sample.source);
  const [copied, setCopied] = useState(false);

  const result = useMemo(
    () => migrateSource(source, { sourcePath: sample.filename }),
    [source, sample.filename],
  );

  const cssCount = result.translations.filter((item) => item.locator.kind === "css").length;
  const xpathCount = result.translations.filter((item) => item.locator.kind === "xpath").length;

  function loadSample(id: (typeof SAMPLES)[number]["id"]) {
    const next = SAMPLES.find((item) => item.id === id) ?? SAMPLES[0];
    setSampleId(next.id);
    setSource(next.source);
  }

  async function copyOutput() {
    await navigator.clipboard.writeText(result.script.python_source);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="mark">
          <b>AutoQL</b>
          <span>Legacy → AgentQL migrator</span>
        </div>
        <div className="top-meta">Live demo · heuristic translator · no API key</div>
      </header>

      <section className="hero">
        <div>
          <h1>
            Brittle locators in.
            <br />
            <em>Semantic queries</em> out.
          </h1>
          <p className="lede">
            Paste a Playwright or Selenium script. The same parse → translate → generate
            pipeline as the CLI rewrites CSS/XPath call sites into an AgentQL
            <code> query_elements</code> script — instantly, in the browser.
          </p>
        </div>
        <div className="steps">
          <div className="step">
            <div className="n">01</div>
            <div>
              <strong>Parse</strong>
              <span>Walk locator(), fill/click, and find_element call sites.</span>
            </div>
          </div>
          <div className="step">
            <div className="n">02</div>
            <div>
              <strong>Translate</strong>
              <span>Name each control from test ids, name, type, then classes.</span>
            </div>
          </div>
          <div className="step">
            <div className="n">03</div>
            <div>
              <strong>Generate</strong>
              <span>Emit a sync Playwright module that queries by role, not path.</span>
            </div>
          </div>
        </div>
      </section>

      <section className="workbench">
        <div className="toolbar">
          <div className="tabs">
            {SAMPLES.map((item) => (
              <button
                key={item.id}
                className="tab"
                data-active={item.id === sampleId}
                onClick={() => loadSample(item.id)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <button className="copy" onClick={copyOutput} type="button">
            {copied ? "Copied" : "Copy AgentQL script"}
          </button>
        </div>

        <div className="grid">
          <div className="pane">
            <div className="pane-head">
              <span>Legacy script</span>
              <span className="chip legacy">{sample.filename}</span>
            </div>
            <div className="editor-wrap">
              <div className="gutter" aria-hidden="true">
                {Array.from({ length: lineCount(source) }, (_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              <textarea
                className="code"
                spellCheck={false}
                value={source}
                onChange={(event) => setSource(event.target.value)}
                aria-label="Legacy Playwright or Selenium script"
              />
            </div>
          </div>

          <div className="pane">
            <div className="pane-head">
              <span>Generated AgentQL</span>
              <span className="chip fresh">{result.script.field_names.length} fields</span>
            </div>
            <div className="editor-wrap">
              <div className="gutter" aria-hidden="true">
                {Array.from({ length: lineCount(result.script.python_source) }, (_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              <pre className="code">{result.script.python_source}</pre>
            </div>
          </div>
        </div>

        <div className="results">
          <div className="results-head">
            <h2>Locator map</h2>
            <div className="stats">
              <span>
                <b>{result.locator_count}</b> locators
              </span>
              <span>
                <b>{cssCount}</b> css
              </span>
              <span>
                <b>{xpathCount}</b> xpath
              </span>
              <span>
                URL <b>{result.script.url}</b>
              </span>
            </div>
          </div>

          <pre className="query">{result.script.query}</pre>

          {result.translations.length === 0 ? (
            <p className="empty">
              No locators found. Use <code>page.locator(&quot;...&quot;).click()</code>,{" "}
              <code>page.fill(&quot;...&quot;, value)</code>, or{" "}
              <code>driver.find_element(By.CSS_SELECTOR, &quot;...&quot;)</code> with literal
              selectors.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Action</th>
                    <th>Kind</th>
                    <th>Brittle selector</th>
                    <th>AgentQL name</th>
                  </tr>
                </thead>
                <tbody>
                  {result.translations.map((item) => (
                    <tr key={`${item.locator.lineno}-${item.name}`}>
                      <td>{item.locator.lineno}</td>
                      <td>{item.locator.interaction}</td>
                      <td>
                        <span className={`kind ${item.locator.kind}`}>{item.locator.kind}</span>
                      </td>
                      <td className="sel">{item.locator.selector}</td>
                      <td className="name">{item.name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="footnote">
            This demo runs the CLI&apos;s heuristic translator in the browser (the same names
            you get from <code>python migrator.py --fallback</code>). The Python CLI can also
            call gpt-4o-mini when <code>OPENAI_API_KEY</code> is set. Generated scripts need{" "}
            <code>AGENTQL_API_KEY</code> at runtime.
          </p>
        </div>
      </section>
    </div>
  );
}
