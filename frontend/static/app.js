(() => {
  const kindOf = (f) => {
    const t = f.type || "";
    if (t.startsWith("image/")) return "image";
    if (t.startsWith("audio/")) return "audio";
    if (t.startsWith("video/")) return "video";
    return "document";
  };
  const size = (b) => b >= 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";

  // Drop zones: preview name/size/type, enforce size limit, set hidden media_kind.
  document.querySelectorAll(".drop").forEach((zone) => {
    const input = zone.querySelector('input[type="file"]');
    const kind = zone.querySelector('input[name="media_kind"]');
    const msg = zone.querySelector(".drop-msg");
    const max = parseFloat(zone.dataset.maxMb || "25") * 1048576;

    const show = () => {
      const f = input.files[0];
      msg.classList.remove("bad");
      zone.classList.remove("has");
      if (kind) kind.value = "";
      if (!f) { msg.textContent = ""; return; }
      if (f.size > max) {
        input.value = "";
        msg.textContent = `${f.name} is ${size(f.size)}. The limit is ${size(max)}.`;
        msg.classList.add("bad");
        return;
      }
      if (kind) kind.value = kindOf(f);
      zone.classList.add("has");
      msg.textContent = `${f.name}, ${kindOf(f)}, ${size(f.size)}`;
    };

    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach((e) => zone.addEventListener(e, (ev) => { ev.preventDefault(); zone.classList.add("over"); }));
    ["dragleave", "drop"].forEach((e) => zone.addEventListener(e, () => zone.classList.remove("over")));
  });

  // Busy state on submit.
  document.querySelectorAll("form[data-busy]").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector('button[type="submit"]');
      if (!btn || !form.checkValidity()) return;
      btn.disabled = true;
      btn.textContent = form.dataset.busy;
    });
  });

  // Copy watermark ID.
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const src = document.querySelector(btn.dataset.copy);
      if (!src) return;
      const label = btn.textContent;
      try {
        await navigator.clipboard.writeText(src.textContent.trim());
        btn.textContent = "Copied";
      } catch {
        btn.textContent = "Copy failed";
      }
      setTimeout(() => (btn.textContent = label), 1500);
    });
  });

  // Landing: file hashes churn and settle; identifiers stay put.
  const strip = document.getElementById("strip");
  if (strip && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const hex = "0123456789abcdef";
    strip.querySelectorAll(".hash").forEach((el, i) => {
      const final = el.dataset.final;
      const start = performance.now() + i * 350;
      const tick = (now) => {
        const t = now - start;
        if (t < 0) return requestAnimationFrame(tick);
        const settled = Math.floor((t / 900) * final.length);
        el.textContent = final.split("").map((c, n) => n < settled ? c : hex[Math.floor(Math.random() * 16)]).join("");
        if (settled < final.length) requestAnimationFrame(tick); else el.textContent = final;
      };
      requestAnimationFrame(tick);
    });
  }
})();