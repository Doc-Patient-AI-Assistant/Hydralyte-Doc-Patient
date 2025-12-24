import React, { useEffect, useState } from "react";

/* ---------------- PROCESS STEPS ---------------- */
const steps = [
  { key: "uploading", label: "Uploading audio", icon: "📤" },
  { key: "transcribing", label: "Transcribing speech", icon: "🎙️" },
  { key: "summarizing", label: "Analyzing conversation", icon: "🧠" },
  { key: "generating_pdf", label: "Generating report", icon: "📄" },
  { key: "completed", label: "Completed", icon: "✅" },
];

/* ---------------- PROGRESS BAR ---------------- */
const ProgressBar = ({ progress }) => (
  <div style={{ marginTop: "12px" }}>
    <div
      style={{
        height: "8px",
        background: "#e5e7eb",
        borderRadius: "4px",
      }}
    >
      <div
        style={{
          width: `${progress || 0}%`,
          height: "8px",
          background: "#4CAF50",
          borderRadius: "4px",
          transition: "width 0.4s ease",
        }}
      />
    </div>
  </div>
);

/* ---------------- STEP TIMELINE ---------------- */
const StepTimeline = ({ status }) => {
  if (!status) return null;

  const currentIndex = steps.findIndex(
    (s) => s.key === status.stage
  );

  return (
    <div style={{ marginTop: "20px" }}>
      {steps.map((step, index) => {
        const isDone = index < currentIndex;
        const isActive = index === currentIndex;

        return (
          <div
            key={step.key}
            style={{
              display: "flex",
              alignItems: "center",
              opacity: isDone || isActive ? 1 : 0.4,
              marginBottom: "8px",
            }}
          >
            <span style={{ fontSize: "18px", marginRight: "10px" }}>
              {step.icon}
            </span>
            <span
              style={{
                fontWeight: isActive ? "bold" : "normal",
              }}
            >
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
};

function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null);
  const [currentFileId, setCurrentFileId] = useState(null);

  /* ---------------- UPLOAD AUDIO ---------------- */
  const uploadAudio = async () => {
    if (!file) {
      alert("Please select an audio file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      // Immediate UX feedback
      setStatus({
        stage: "uploading",
        message: "Uploading audio",
        progress: 10,
      });

      const res = await fetch("http://localhost:8000/upload-audio", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setCurrentFileId(data.audio_name);

    } catch (err) {
      console.error(err);
      alert("Upload failed");
    }
  };

  /* ---------------- POLL BACKEND STATUS ---------------- */
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("http://localhost:8000/status");
        const data = await res.json();
        setStatus(data);
      } catch (e) {
        console.error("Status polling failed");
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  /* ---------------- RENDER STATUS MESSAGE ---------------- */
  const renderStageMessage = () => {
    if (!currentFileId) return "Waiting for audio…";
    if (!status) return "Waiting for audio…";

    // Ignore other files (Bluetooth etc.)
    if (status.file !== currentFileId) {
      return "Waiting for audio…";
    }

    return status.message || "Processing…";
  };

  const isCurrentFileCompleted =
    status?.stage === "completed" &&
    status?.file === currentFileId;

  return (
    <div
      style={{
        padding: "40px",
        fontFamily: "Arial, sans-serif",
        maxWidth: "600px",
        margin: "0 auto",
      }}
    >
      <h2>Doctor–Patient Audio Processing</h2>

      {/* -------- FILE INPUT -------- */}
      <input
        type="file"
        accept="audio/*"
        onChange={(e) => setFile(e.target.files[0])}
      />

      <br /><br />

      <button
        onClick={uploadAudio}
        style={{
          padding: "10px 16px",
          borderRadius: "6px",
          border: "none",
          background: "#2563eb",
          color: "white",
          cursor: "pointer",
        }}
      >
        Upload Audio
      </button>

      <hr style={{ margin: "30px 0" }} />

      {/* -------- STATUS -------- */}
      <h3>Status</h3>

      <p style={{ fontSize: "16px" }}>
        {renderStageMessage()}
      </p>

      {status?.file === currentFileId && (
        <>
          <ProgressBar progress={status.progress} />
          <StepTimeline status={status} />

          <p style={{ marginTop: "12px", fontSize: "14px", color: "#555" }}>
            <b>File:</b> {status.file}
            <br />
            <b>Source:</b> {status.source}
          </p>
        </>
      )}

      {/* -------- PDF DOWNLOAD -------- */}
      {isCurrentFileCompleted && (
        <a
          href={`http://localhost:8000/download-pdf/${currentFileId}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-block",
            marginTop: "24px",
            padding: "12px 18px",
            backgroundColor: "#16a34a",
            color: "white",
            textDecoration: "none",
            borderRadius: "6px",
            fontWeight: "bold",
          }}
        >
          📄 Download Summary PDF
        </a>
      )}

      {/* -------- BLUETOOTH INFO -------- */}
      <div
        style={{
          marginTop: "40px",
          fontSize: "14px",
          color: "#555",
        }}
      >
        <h4>Bluetooth Upload</h4>
        <p>
          Send audio from your phone via Bluetooth.<br />
          Windows saves it automatically and processing starts on its own.
        </p>
      </div>
    </div>
  );
}

export default App;
