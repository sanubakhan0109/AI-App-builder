import { useState } from "react";

function App() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState("");

  const BACKEND_URL = "https://ai-app-builder-c25a.onrender.com";

  const generateApp = async () => {
    if (!prompt.trim()) return;

    setLoading(true);
    setError("");
    setFiles([]);
    setSelectedFile(null);

    try {
      const response = await fetch(`${BACKEND_URL}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: prompt,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to generate application");
      }

      const data = await response.json();

      setFiles(data.files);

      if (data.files.length > 0) {
        setSelectedFile(data.files[0]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openGeneratedApp = () => {
    window.open(
      `${BACKEND_URL}/preview/index.html`,
      "_blank"
    );
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">

      {/* Header */}
      <header className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-xl font-semibold">
            AI App Builder
          </h1>

          <div className="text-sm text-gray-400">
            Mistral × LangGraph
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto max-w-7xl px-6 py-10">

        {/* Prompt Section */}
        <section className="mx-auto max-w-3xl">

          <h2 className="mb-3 text-center text-4xl font-bold">
            Build an app with AI
          </h2>

          <p className="mb-8 text-center text-gray-400">
            Describe what you want to build and let the agents handle the rest.
          </p>

          {/* Prompt Box */}
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Create a modern todo application..."
              className="h-32 w-full resize-none bg-transparent p-3 text-white outline-none placeholder:text-gray-600"
            />

            <div className="flex justify-end">

              <button
                onClick={generateApp}
                disabled={loading}
                className="rounded-xl bg-white px-5 py-2.5 font-medium text-black transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Building..." : "Generate App →"}
              </button>

            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400">
              {error}
            </div>
          )}

        </section>

        {/* Generated Project */}
        {files.length > 0 && (
          <section className="mt-12">

            {/* Project Header */}
            <div className="mb-5 flex items-center justify-between">

              <div>
                <h2 className="text-xl font-semibold">
                  Generated Project
                </h2>

                <p className="text-sm text-gray-500">
                  {files.length} files generated
                </p>
              </div>

              {/* Open App Button */}
              <button
                onClick={openGeneratedApp}
                className="rounded-xl bg-white px-5 py-2.5 font-medium text-black transition hover:bg-gray-200"
              >
                Open App
              </button>

            </div>

            {/* File Explorer + Code Viewer */}
            <div className="grid min-h-[500px] grid-cols-[220px_1fr] overflow-hidden rounded-2xl border border-white/10 bg-[#111111]">

              {/* File Explorer */}
              <aside className="border-r border-white/10">

                <div className="border-b border-white/10 px-4 py-3 text-sm font-medium">
                  Project
                </div>

                <div className="p-2">

                  {files.map((file) => (
                    <button
                      key={file.path}
                      onClick={() => setSelectedFile(file)}
                      className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                        selectedFile?.path === file.path
                          ? "bg-white/10 text-white"
                          : "text-gray-400 hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      {file.path}
                    </button>
                  ))}

                </div>

              </aside>

              {/* Code Viewer */}
              <div className="flex flex-col">

                <div className="border-b border-white/10 px-5 py-3 text-sm text-gray-300">
                  {selectedFile?.path || "Select a file"}
                </div>

                <pre className="flex-1 overflow-auto p-6 text-sm leading-6 text-gray-300">
                  <code>
                    {selectedFile?.content || "No file selected"}
                  </code>
                </pre>

              </div>

            </div>

          </section>
        )}

      </main>

    </div>
  );
}

export default App;