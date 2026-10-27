import { useRef, useState } from "react";
import "./App.css";

const BACKEND_URL = "http://127.0.0.1:8000";
const GENERATION_TIMEOUT_MS = 60_000;
const GENERATION_TIMEOUT_MESSAGE = "Generation took too long. Please try again.";

function AssistantAvatar({ status }) {
  const messages = {
    idle: "Waiting for your idea...",
    generating: "Generating your app...",
    success: "Your app is ready!",
    error: "That didn’t go as planned. Try again?",
  };

  return (
    <div className={`assistant-status assistant-status--${status}`} aria-live="polite">
      <div className="avatar-stage" aria-hidden="true">
        <span className="avatar-orbit avatar-orbit--one" />
        <span className="avatar-orbit avatar-orbit--two" />
        <span className="avatar-spark avatar-spark--one" />
        <span className="avatar-spark avatar-spark--two" />
        <div className="avatar">
          <span className="avatar-antenna" />
          <span className="avatar-ear avatar-ear--left" />
          <span className="avatar-ear avatar-ear--right" />
          <div className="avatar-face">
            <span className="avatar-eye avatar-eye--left" />
            <span className="avatar-eye avatar-eye--right" />
            <span className="avatar-smile" />
          </div>
          <span className="avatar-neck" />
          <span className="avatar-body">
            <span className="avatar-core" />
          </span>
        </div>
      </div>
      <div className="assistant-copy">
        <p className="assistant-message">{messages[status]}</p>
        {status === "generating" && (
          <span className="assistant-progress" aria-label="Generation in progress">
            <i />
            <i />
            <i />
          </span>
        )}
      </div>
    </div>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M4.25 10h11.5m-4.75-4.75L15.75 10 11 14.75" />
    </svg>
  );
}

function App() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("idle");
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState("");
  const requestInProgress = useRef(false);

  const generateApp = async () => {
    if (!prompt.trim() || requestInProgress.current) return;

    requestInProgress.current = true;
    const controller = new AbortController();
    let didTimeout = false;
    let timeoutId;
    setLoading(true);
    setStatus("generating");
    setError("");
    setFiles([]);
    setSelectedFile(null);

    try {
      const request = (async () => {
        const response = await fetch(`${BACKEND_URL}/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ prompt: prompt.trim() }),
          signal: controller.signal,
        });

        let responseBody;
        try {
          responseBody = await response.json();
        } catch {
          throw new Error(
            response.ok
              ? "The builder returned an invalid response. Please try again."
              : `Generation failed (${response.status}). Please try again.`,
          );
        }

        if (!response.ok) {
          throw new Error(responseBody.detail || responseBody.message || `Generation failed (${response.status}). Please try again.`);
        }

        return responseBody;
      })();

      const deadline = new Promise((_, reject) => {
        timeoutId = window.setTimeout(() => {
          didTimeout = true;
          controller.abort();
          const timeoutError = new Error(GENERATION_TIMEOUT_MESSAGE);
          timeoutError.name = "GenerationTimeoutError";
          reject(timeoutError);
        }, GENERATION_TIMEOUT_MS);
      });

      const data = await Promise.race([request, deadline]);
      if (!Array.isArray(data.files) || data.files.length === 0) {
        throw new Error("Generation finished, but no project files were returned. Please try again.");
      }

      setFiles(data.files);
      const defaultFile = data.files.find((f) => f.path === "index.html" || f.path.endsWith("/index.html")) || data.files[0];
      setSelectedFile(defaultFile);
      setStatus("success");
    } catch (requestError) {
      const message = didTimeout || requestError.name === "AbortError"
        ? GENERATION_TIMEOUT_MESSAGE
        : requestError.message || "Couldn’t connect to the builder. Check your connection and try again.";
      setError(message);
      setStatus("error");
    } finally {
      window.clearTimeout(timeoutId);
      controller.abort();
      requestInProgress.current = false;
      setLoading(false);
    }
  };

  const handlePromptChange = (event) => {
    setPrompt(event.target.value);
    if (status === "error") {
      setError("");
      setStatus("idle");
    }
  };

  const handlePromptKeyDown = (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      generateApp();
    }
  };

  const openGeneratedApp = () => {
    window.open(`${BACKEND_URL}/preview/index.html`, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="app-shell">
      <div className="ambient ambient--top" aria-hidden="true" />
      <div className="ambient ambient--bottom" aria-hidden="true" />

      <header className="topbar">
        <a className="brand" href="#" aria-label="AI App Builder home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </span>
          <span>AI <strong>App Builder</strong></span>
        </a>
        <div className="engine-badge">
          <span className="engine-indicator" />
          <span>Powered by Gemini × LangGraph</span>
        </div>
      </header>

      <main className="main-content">
        <section className="hero" aria-labelledby="page-title">
          <div className="eyebrow"><span /> YOUR NEXT BIG IDEA STARTS HERE</div>
          <h1 id="page-title">AI App <span>Builder</span></h1>
          <p className="hero-subtitle">Turn your ideas into working applications.</p>
          <p className="hero-description">
            Describe what you have in mind. Your AI team will take it from idea to app.
          </p>

          <div className="composer">
            <label className="sr-only" htmlFor="app-prompt">Describe the app you want to build</label>
            <textarea
              id="app-prompt"
              value={prompt}
              onChange={handlePromptChange}
              onKeyDown={handlePromptKeyDown}
              placeholder="Describe the app you want to build..."
              maxLength={4000}
              disabled={loading}
            />
            <div className="composer-footer">
              <span className="keyboard-hint"><kbd>Ctrl</kbd><span>+</span><kbd>Enter</kbd> to generate</span>
              <button
                type="button"
                onClick={generateApp}
                disabled={!prompt.trim() || loading}
                className="generate-button"
              >
                {loading ? (
                  <>
                    <span className="button-spinner" aria-hidden="true" />
                    Building
                  </>
                ) : (
                  <>Generate app <ArrowIcon /></>
                )}
              </button>
            </div>
          </div>

          <AssistantAvatar status={status} />

          {error && (
            <div className="error-message" role="alert">
              <span className="error-icon" aria-hidden="true">!</span>
              <p>{error}</p>
            </div>
          )}

          {status === "idle" && (
            <div className="prompt-suggestion">
              <span>Try</span>
              <button
                type="button"
                onClick={() => setPrompt("Build a modern ecommerce website with product cards, search, and a shopping cart.")}
              >
                “Build a modern ecommerce website with product cards and a shopping cart”
              </button>
            </div>
          )}
        </section>

        {files.length > 0 && (
          <section className="project-section" aria-labelledby="project-title">
            <div className="project-heading">
              <div>
                <div className="project-kicker"><span className="success-dot" /> GENERATION COMPLETE</div>
                <h2 id="project-title">Your project</h2>
                <p>{files.length} {files.length === 1 ? "file" : "files"} created from your idea</p>
              </div>
              <button type="button" onClick={openGeneratedApp} className="preview-button">
                Open live preview <ArrowIcon />
              </button>
            </div>

            <div className="project-workspace">
              <aside className="file-sidebar" aria-label="Generated project files">
                <div className="sidebar-heading">
                  <span className="folder-icon" aria-hidden="true">▰</span>
                  <span>PROJECT FILES</span>
                  <span className="file-count">{files.length}</span>
                </div>
                <div className="file-list">
                  {files.map((file) => (
                    <button
                      type="button"
                      key={file.path}
                      onClick={() => setSelectedFile(file)}
                      className={`file-item${selectedFile?.path === file.path ? " is-selected" : ""}`}
                      title={file.path}
                    >
                      <span className="file-icon" aria-hidden="true">{file.path.split(".").pop()?.slice(0, 2).toUpperCase()}</span>
                      <span>{file.path}</span>
                    </button>
                  ))}
                </div>
              </aside>
              <div className="code-panel">
                <div className="code-toolbar">
                  <div className="window-dots" aria-hidden="true"><i /><i /><i /></div>
                  <span>{selectedFile?.path || "Select a file"}</span>
                  <span className="code-language">SOURCE</span>
                </div>
                <pre className="code-content"><code>{selectedFile?.content || "No file selected"}</code></pre>
              </div>
            </div>
          </section>
        )}
      </main>

      <footer className="page-footer">
        <span>Built for the ideas you can’t stop thinking about.</span>
        <span className="footer-status"><span /> AI agents ready</span>
      </footer>
    </div>
  );
}

export default App;
