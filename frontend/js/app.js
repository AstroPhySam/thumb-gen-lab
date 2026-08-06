const API = "http://localhost:8000";

const dropZone = document.getElementById("drop-zone");
const pickBtn = document.getElementById("pick-btn");
const fileInput = document.getElementById("file-input");
const previewWrap = document.getElementById("preview-wrap");
const preview = document.getElementById("preview");
const statusBox = document.getElementById("status");
const statusBadge = document.getElementById("status-badge");
const statusText = document.getElementById("status-text");
const errorBox = document.getElementById("error");
const downloadLink = document.getElementById("download-link");

let source = null;

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

pickBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) handleFile(file);
});

function handleFile(file) {
  if (!file.type.startsWith("image/")) {
    showError("Only image files are supported.");
    return;
  }
  reset();
  preview.src = URL.createObjectURL(file);
  previewWrap.classList.remove("hidden");
  setStatus("queued", "Uploading...");
  upload(file);
}

async function upload(file) {
  const formData = new FormData();
  formData.append("file", file);

  let jobId;
  try {
    const res = await fetch(`${API}/api/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `Upload failed (${res.status})`);
    }
    const data = await res.json();
    jobId = data.job_id;
  } catch (err) {
    showError(`Upload failed: ${err.message}`);
    return;
  }

  listen(jobId);
}

function listen(jobId) {
  setStatus("queued", "Queued for processing...");
  source = new EventSource(`${API}/api/events/${jobId}`);

  source.addEventListener("queued", () =>
    setStatus("queued", "Queued for processing..."),
  );
  source.addEventListener("processing", () =>
    setStatus("processing", "Generating thumbnails..."),
  );
  source.addEventListener("done", (e) => {
    const data = JSON.parse(e.data);
    setStatus("done", "Thumbnails ready.");
    downloadLink.href = `${API}${data.download_url}`;
    downloadLink.classList.remove("hidden");
    closeStream();
  });
  source.addEventListener("failed", (e) => {
    const data = JSON.parse(e.data);
    setStatus("failed", "Processing failed.");
    showError(data.error || "Unknown error.");
    closeStream();
  });

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) return;
    setStatus("processing", "Reconnecting...");
  };
}

function setStatus(state, text) {
  statusBadge.textContent = state.toUpperCase();
  statusBadge.className = "badge " + state;
  statusText.textContent = text;
  statusBox.classList.remove("hidden");
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function closeStream() {
  if (source) {
    source.close();
    source = null;
  }
}

function reset() {
  closeStream();
  errorBox.classList.add("hidden");
  downloadLink.classList.add("hidden");
  downloadLink.href = "#";
  statusBox.classList.add("hidden");
}
