document.addEventListener("DOMContentLoaded", () => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content || "";

    document.querySelectorAll(".datatable").forEach((table) => {
        if (window.jQuery && $.fn.DataTable) {
            $(table).DataTable({ responsive: true, pageLength: 10 });
        }
    });

    document.querySelectorAll(".confirm-form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!confirm("Delete this record?")) {
                event.preventDefault();
            }
        });
    });

    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.querySelector(".sidebar");
    sidebarToggle?.addEventListener("click", () => sidebar?.classList.toggle("open"));

    const themeToggle = document.getElementById("themeToggle");
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) document.documentElement.setAttribute("data-bs-theme", savedTheme);
    themeToggle?.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-bs-theme") || "light";
        const next = current === "light" ? "dark" : "light";
        document.documentElement.setAttribute("data-bs-theme", next);
        localStorage.setItem("theme", next);
    });

    const imageInput = document.getElementById("imageInput");
    const previewGrid = document.getElementById("previewGrid");
    imageInput?.addEventListener("change", () => {
        previewGrid.innerHTML = "";
        [...imageInput.files].forEach((file) => {
            const img = document.createElement("img");
            img.src = URL.createObjectURL(file);
            img.onload = () => URL.revokeObjectURL(img.src);
            previewGrid.appendChild(img);
        });
    });

    const singleInput = document.getElementById("singleImageInput");
    const singlePreview = document.getElementById("singlePreview");
    singleInput?.addEventListener("change", () => {
        const file = singleInput.files[0];
        if (!file) return;
        singlePreview.src = URL.createObjectURL(file);
        singlePreview.classList.remove("d-none");
    });

    const chartCanvas = document.getElementById("attendanceChart");
    if (chartCanvas && window.Chart) {
        new Chart(chartCanvas, {
            type: "doughnut",
            data: {
                labels: JSON.parse(chartCanvas.dataset.labels),
                datasets: [{
                    data: JSON.parse(chartCanvas.dataset.values),
                    backgroundColor: ["#16a34a", "#dc2626", "#f59e0b"],
                    borderWidth: 0
                }]
            },
            options: { plugins: { legend: { position: "bottom" } } }
        });
    }

    document.querySelectorAll(".export-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const form = document.getElementById("reportForm");
            const params = new URLSearchParams(new FormData(form));
            window.location.href = `/reports/${button.dataset.format}?${params.toString()}`;
        });
    });

    const video = document.getElementById("webcamVideo");
    const canvas = document.getElementById("webcamCanvas");
    const startCamera = document.getElementById("startCamera");
    const captureAttendance = document.getElementById("captureAttendance");
    const autoScanToggle = document.getElementById("autoScanToggle");
    const webcamResult = document.getElementById("webcamResult");
    let stream = null;
    let autoScanTimer = null;
    let isProcessing = false;

    startCamera?.addEventListener("click", async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
            video.srcObject = stream;
            webcamResult.innerHTML = '<div class="alert alert-info py-2"><i class="fa-solid fa-camera me-2"></i>Camera active. Position face towards the screen.</div>';
        } catch (error) {
            webcamResult.innerHTML = `<div class="alert alert-danger py-2">Camera access failed: ${error.message}</div>`;
        }
    });

    async function performWebcamCapture(isAuto = false) {
        if (!stream) {
            if (!isAuto) webcamResult.innerHTML = '<div class="alert alert-warning py-2">Please start the camera first.</div>';
            return;
        }
        if (isProcessing) return;
        isProcessing = true;

        if (!isAuto) {
            webcamResult.innerHTML = '<div class="alert alert-info py-2"><i class="fa-solid fa-spinner fa-spin me-2"></i>Analyzing face and verifying biometric ID...</div>';
        }

        try {
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            canvas.getContext("2d").drawImage(video, 0, 0);

            const response = await fetch("/attendance/webcam", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": token },
                body: JSON.stringify({ image: canvas.toDataURL("image/jpeg", 0.92) })
            });
            const data = await response.json();
            if (!data.ok) {
                webcamResult.innerHTML = `<div class="alert alert-danger py-2">${data.message}</div>`;
                return;
            }

            if (data.recognized && data.recognized.length > 0) {
                const studentPills = data.recognized.map((s) => `
                    <div class="d-inline-flex align-items-center gap-2 bg-success text-white px-3 py-1 rounded-pill me-2 mb-2">
                        <i class="fa-solid fa-circle-check"></i>
                        <strong>${s.name}</strong> (${s.roll_number})
                        <span class="badge bg-white text-success">${s.confidence}% Match</span>
                    </div>
                `).join("");

                webcamResult.innerHTML = `
                    <div class="alert alert-success mb-2 py-2">
                        <i class="fa-solid fa-check-circle me-1"></i> Attendance Marked <strong>PRESENT</strong>!
                    </div>
                    <div class="mb-2">${studentPills}</div>
                    <div class="summary-row mb-2">
                        <span>Faces: <strong>${data.summary.faces_detected}</strong></span>
                        <span>Recognized: <strong>${data.summary.recognized_count}</strong></span>
                        <span>Unknown: <strong>${data.summary.unknown_count}</strong></span>
                    </div>
                    ${data.processed_image ? `<img class="processed-image shadow-sm rounded mt-2" src="${data.processed_image}" alt="Processed webcam frame">` : ""}
                `;
            } else if (data.summary.faces_detected > 0) {
                webcamResult.innerHTML = `
                    <div class="alert alert-warning py-2 mb-2">
                        <i class="fa-solid fa-triangle-exclamation me-1"></i>
                        <strong>Face Detected, but Not Recognized.</strong>
                        <div class="small mt-1 text-muted">The face in frame does not match any registered student profile. Ensure your student profile has clear face photos uploaded.</div>
                    </div>
                    <div class="summary-row mb-2">
                        <span>Faces: <strong>${data.summary.faces_detected}</strong></span>
                        <span>Recognized: 0</span>
                        <span>Unknown: <strong>${data.summary.unknown_count}</strong></span>
                    </div>
                    ${data.processed_image ? `<img class="processed-image shadow-sm rounded mt-2" src="${data.processed_image}" alt="Processed webcam frame">` : ""}
                `;
            } else {
                if (!isAuto) {
                    webcamResult.innerHTML = `
                        <div class="alert alert-secondary py-2">
                            <i class="fa-solid fa-eye-slash me-1"></i> No face detected in camera frame. Look directly at the camera.
                        </div>
                    `;
                }
            }
        } catch (err) {
            webcamResult.innerHTML = `<div class="alert alert-danger py-2">Recognition error: ${err.message}</div>`;
        } finally {
            isProcessing = false;
        }
    }

    captureAttendance?.addEventListener("click", () => performWebcamCapture(false));

    autoScanToggle?.addEventListener("change", (e) => {
        if (e.target.checked) {
            if (!stream) {
                startCamera?.click();
            }
            autoScanTimer = setInterval(() => performWebcamCapture(true), 2500);
        } else {
            if (autoScanTimer) {
                clearInterval(autoScanTimer);
                autoScanTimer = null;
            }
        }
    });
});
