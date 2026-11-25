const mobileQuery = window.matchMedia("(max-width: 71.99rem)");
const bar = document.querySelector(".plot-bar");
const toc = document.querySelector(".toc");
const navToggle = document.querySelector("#nav-toggle");
const tocList = document.querySelector("#toc-list");
const navLinks = [...document.querySelectorAll(".toc a")];
const sections = [...document.querySelectorAll("main > header, main > section")];

/* ---------- Contents ---------- */

function navigationIsOpen() {
  return navToggle?.getAttribute("aria-expanded") === "true";
}

function setNavigationOpen(open, restoreFocus = false) {
  if (!navToggle || !tocList) return;
  navToggle.setAttribute("aria-expanded", String(open));
  tocList.classList.toggle("is-open", open);
  if (restoreFocus) navToggle.focus();
}

navToggle?.addEventListener("click", () => setNavigationOpen(!navigationIsOpen()));

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && navigationIsOpen()) setNavigationOpen(false, true);
});

document.addEventListener("click", (event) => {
  if (!navigationIsOpen() || !mobileQuery.matches) return;
  if (!toc?.contains(event.target)) setNavigationOpen(false);
});

mobileQuery.addEventListener("change", () => setNavigationOpen(false));

/* ---------- Current section ---------- */

const linkById = new Map(
  navLinks.map((link) => [decodeURIComponent(link.hash.slice(1)), link]),
);
let currentSectionId;

function markCurrent(id) {
  const link = linkById.get(id);
  if (id !== currentSectionId) {
    currentSectionId = id;
    navLinks.forEach((navLink) => navLink.removeAttribute("aria-current"));
    if (link) link.setAttribute("aria-current", "true");
  }
  if (!link || mobileQuery.matches || !toc) return;
  const linkBox = link.getBoundingClientRect();
  const tocBox = toc.getBoundingClientRect();
  if (linkBox.top < tocBox.top || linkBox.bottom > tocBox.bottom) {
    link.scrollIntoView({ block: "nearest" });
  }
}

function headerOffset() {
  const barHeight = bar ? bar.getBoundingClientRect().height : 0;
  const tocHeight = mobileQuery.matches && toc
    ? toc.getBoundingClientRect().height
    : 0;
  return barHeight + tocHeight + 16;
}

function updateCurrentSection() {
  const line = headerOffset() + 24;
  let current = "";
  for (const section of sections) {
    if (section.getBoundingClientRect().top > line) break;
    current = section.id;
  }
  markCurrent(current);
}

let spyFrame = 0;
function scheduleSectionUpdate() {
  if (spyFrame) return;
  spyFrame = window.requestAnimationFrame(() => {
    spyFrame = 0;
    updateCurrentSection();
  });
}

window.addEventListener("scroll", scheduleSectionUpdate, { passive: true });
window.addEventListener("resize", scheduleSectionUpdate);
updateCurrentSection();

/* ---------- Anchors ---------- */

function positionAnchor(target, behavior = "smooth") {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) behavior = "auto";
  const top = window.scrollY + target.getBoundingClientRect().top - headerOffset();
  window.scrollTo({ top: Math.max(0, top), behavior });
}

function focusAnchorTarget(target) {
  if (!target.hasAttribute("tabindex")) {
    target.setAttribute("tabindex", "-1");
    target.addEventListener("blur", () => target.removeAttribute("tabindex"), { once: true });
  }
  target.focus({ preventScroll: true });
}

function targetForHash(hash) {
  const id = decodeURIComponent(hash.slice(1));
  return id ? document.getElementById(id) : null;
}

document.addEventListener("click", (event) => {
  const link = event.target.closest?.('a[href^="#"]');
  if (!link || link.classList.contains("skip-link")) return;
  const target = targetForHash(link.hash);
  if (!target) return;
  event.preventDefault();
  if (mobileQuery.matches && navigationIsOpen()) setNavigationOpen(false);
  history.replaceState(null, "", link.hash);
  positionAnchor(target);
  focusAnchorTarget(target);
  updateCurrentSection();
});

function alignToLocationHash() {
  const target = targetForHash(location.hash);
  if (target) positionAnchor(target, "auto");
}

window.addEventListener("hashchange", alignToLocationHash);

window.addEventListener("load", () => {
  alignToLocationHash();
  updateCurrentSection();
});
